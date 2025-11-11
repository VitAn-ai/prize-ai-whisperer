import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const { text } = await req.json();
    
    if (!text || text.length < 10) {
      return new Response(
        JSON.stringify({ 
          is_giveaway: false, 
          confidence: 0,
          error: 'Текст слишком короткий для анализа'
        }),
        { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      );
    }

    const LOVABLE_API_KEY = Deno.env.get('LOVABLE_API_KEY');
    if (!LOVABLE_API_KEY) {
      throw new Error('LOVABLE_API_KEY не настроен');
    }

    console.log('Анализируем текст:', text.substring(0, 100) + '...');

    // Вызываем Lovable AI для анализа
    const aiResponse = await fetch('https://ai.gateway.lovable.dev/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${LOVABLE_API_KEY}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: 'google/gemini-2.5-flash',
        messages: [
          {
            role: 'system',
            content: `Ты эксперт по анализу конкурсов и розыгрышей в Telegram. 
Твоя задача - определить, является ли текст описанием конкурса/розыгрыша и извлечь ключевую информацию.

Ответь строго в формате JSON без дополнительного текста:
{
  "is_giveaway": true/false,
  "confidence": число от 0 до 100,
  "title": "название конкурса",
  "description": "краткое описание",
  "prizes": ["приз1", "приз2"],
  "conditions": ["условие1", "условие2"],
  "channels": ["@канал1", "@канал2"],
  "date": "ДД.ММ.ГГГГ или null"
}

Критерии конкурса:
- Упоминание слов: розыгрыш, конкурс, раздача, приз, выиграть, giveaway
- Условия участия: подписка, лайк, репост, комментарий
- Указание приза
- Срок проведения
- Призыв к участию`
          },
          {
            role: 'user',
            content: `Проанализируй этот текст:\n\n${text}`
          }
        ],
        temperature: 0.3,
        max_tokens: 500
      }),
    });

    if (!aiResponse.ok) {
      if (aiResponse.status === 429) {
        throw new Error('Превышен лимит запросов AI. Попробуйте позже.');
      }
      if (aiResponse.status === 402) {
        throw new Error('Недостаточно средств для AI запросов.');
      }
      const errorText = await aiResponse.text();
      console.error('AI ошибка:', aiResponse.status, errorText);
      throw new Error('Ошибка AI анализа');
    }

    const aiData = await aiResponse.json();
    console.log('AI ответ:', JSON.stringify(aiData));

    let analysisResult;
    try {
      // Извлекаем текст ответа
      let responseText = aiData.choices?.[0]?.message?.content || '';
      
      // Очищаем от markdown блоков если есть
      responseText = responseText.trim();
      if (responseText.startsWith('```json')) {
        responseText = responseText.slice(7);
      }
      if (responseText.startsWith('```')) {
        responseText = responseText.slice(3);
      }
      if (responseText.endsWith('```')) {
        responseText = responseText.slice(0, -3);
      }
      responseText = responseText.trim();

      analysisResult = JSON.parse(responseText);
      
      // Валидация и нормализация результата
      if (typeof analysisResult.is_giveaway !== 'boolean') {
        analysisResult.is_giveaway = false;
      }
      if (typeof analysisResult.confidence !== 'number') {
        analysisResult.confidence = 0;
      }
      
      console.log('Результат анализа:', JSON.stringify(analysisResult));

    } catch (parseError) {
      console.error('Ошибка парсинга AI ответа:', parseError);
      // Возвращаем базовый анализ
      analysisResult = performBasicAnalysis(text);
    }

    return new Response(JSON.stringify(analysisResult), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });

  } catch (error) {
    console.error('Ошибка analyze-contest:', error);
    
    // В случае ошибки возвращаем базовый анализ
    const { text } = await req.json();
    const basicResult = performBasicAnalysis(text);
    
    return new Response(JSON.stringify(basicResult), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }
});

// Базовый анализ без AI (fallback)
function performBasicAnalysis(text: string) {
  const textLower = text.toLowerCase();
  
  const keywords = ['розыгрыш', 'конкурс', 'раздача', 'giveaway', 'приз', 'выиграть'];
  const keywordCount = keywords.filter(k => textLower.includes(k)).length;
  
  const channelRegex = /@[\w_]+/g;
  const channels = text.match(channelRegex) || [];
  
  const dateRegex = /\b\d{1,2}[./]\d{1,2}[./]\d{2,4}\b/g;
  const dates = text.match(dateRegex) || [];
  
  const prizeKeywords = ['iphone', 'macbook', 'руб', 'долл', 'приз', 'подарок'];
  const prizeCount = prizeKeywords.filter(p => textLower.includes(p)).length;
  
  let confidence = 0;
  confidence += keywordCount * 25;
  confidence += channels.length * 10;
  confidence += dates.length * 15;
  confidence += prizeCount * 15;
  confidence = Math.min(confidence, 100);
  
  const isGiveaway = confidence >= 40;
  
  return {
    is_giveaway: isGiveaway,
    confidence: confidence,
    title: isGiveaway ? text.split('\n')[0].substring(0, 100) : null,
    description: isGiveaway ? 'Базовый анализ' : null,
    prizes: [],
    conditions: [],
    channels: channels,
    date: dates[0] || null,
    fallback: true
  };
}
