import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

interface TelegramUpdate {
  message?: {
    message_id: number;
    from: {
      id: number;
      first_name: string;
      username?: string;
    };
    chat: {
      id: number;
    };
    text?: string;
    photo?: Array<{
      file_id: string;
    }>;
  };
  callback_query?: {
    id: string;
    from: {
      id: number;
      first_name: string;
      username?: string;
    };
    message: {
      chat: {
        id: number;
      };
      message_id: number;
    };
    data: string;
  };
}

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const BOT_TOKEN = Deno.env.get('TELEGRAM_BOT_TOKEN');
    if (!BOT_TOKEN) {
      throw new Error('TELEGRAM_BOT_TOKEN не настроен');
    }

    const supabaseUrl = Deno.env.get('SUPABASE_URL')!;
    const supabaseKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
    const supabase = createClient(supabaseUrl, supabaseKey);

    const update: TelegramUpdate = await req.json();
    console.log('Получено обновление:', JSON.stringify(update));

    // Обработка callback запросов
    if (update.callback_query) {
      const { callback_query } = update;
      const userId = callback_query.from.id;
      const chatId = callback_query.message.chat.id;
      const data = callback_query.data;

      if (data.startsWith('participate_')) {
        const contestId = data.replace('participate_', '');
        
        // Сохраняем участие
        const { error } = await supabase
          .from('user_participations')
          .insert({
            user_id: userId,
            contest_id: contestId,
            telegram_username: callback_query.from.username,
            telegram_first_name: callback_query.from.first_name
          });

        if (error) {
          console.error('Ошибка сохранения участия:', error);
        }

        // Отправляем подтверждение
        await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/answerCallbackQuery`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            callback_query_id: callback_query.id,
            text: '✅ Вы зарегистрированы в конкурсе!',
            show_alert: false
          })
        });

        await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/editMessageReplyMarkup`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            chat_id: chatId,
            message_id: callback_query.message.message_id,
            reply_markup: {
              inline_keyboard: [[
                { text: '✅ Вы участвуете', callback_data: 'already_participating' }
              ]]
            }
          })
        });
      }

      return new Response(JSON.stringify({ ok: true }), {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      });
    }

    // Обработка текстовых сообщений
    if (update.message?.text) {
      const { message } = update;
      const userId = message.from.id;
      const chatId = message.chat.id;
      const text = message.text;

      console.log(`Сообщение от ${userId}: ${text}`);

      // Команда /start
      if (text === '/start') {
        await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            chat_id: chatId,
            text: `👋 Привет, ${message.from.first_name}!\n\n🎁 Prize AI Whisperer - твой умный помощник для участия в конкурсах!\n\n📝 Просто пересылай мне сообщения с конкурсами, и я автоматически их распознаю и помогу тебе участвовать!\n\n✨ Используй /contests для просмотра активных конкурсов`,
            parse_mode: 'HTML'
          })
        });

        return new Response(JSON.stringify({ ok: true }), {
          headers: { ...corsHeaders, 'Content-Type': 'application/json' }
        });
      }

      // Команда /contests
      if (text === '/contests') {
        const { data: contests } = await supabase
          .from('contests')
          .select('*')
          .eq('status', 'active')
          .order('created_at', { ascending: false })
          .limit(10);

        if (!contests || contests.length === 0) {
          await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              chat_id: chatId,
              text: '📭 Пока нет активных конкурсов. Пересылайте мне сообщения с конкурсами!',
              parse_mode: 'HTML'
            })
          });
        } else {
          for (const contest of contests) {
            const keyboard = {
              inline_keyboard: [[
                { text: '🎯 Участвовать', callback_data: `participate_${contest.id}` }
              ]]
            };

            let messageText = `🎁 <b>${contest.title}</b>\n\n`;
            if (contest.description) {
              messageText += `📝 ${contest.description}\n\n`;
            }
            if (contest.prizes && contest.prizes.length > 0) {
              messageText += `🏆 Призы:\n${contest.prizes.map((p: string) => `  • ${p}`).join('\n')}\n\n`;
            }
            if (contest.end_date) {
              const endDate = new Date(contest.end_date);
              messageText += `⏰ До: ${endDate.toLocaleDateString('ru-RU')}\n\n`;
            }
            messageText += `📊 Уверенность: ${contest.confidence_score}%`;

            await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                chat_id: chatId,
                text: messageText,
                parse_mode: 'HTML',
                reply_markup: keyboard
              })
            });
          }
        }

        return new Response(JSON.stringify({ ok: true }), {
          headers: { ...corsHeaders, 'Content-Type': 'application/json' }
        });
      }

      // Анализируем сообщение на наличие конкурса
      try {
        const { data: analysisData, error: analysisError } = await supabase.functions.invoke('analyze-contest', {
          body: { text }
        });

        if (analysisError) throw analysisError;

        if (analysisData?.is_giveaway && analysisData.confidence >= 40) {
          // Сохраняем конкурс в БД
          const { data: contest, error: insertError } = await supabase
            .from('contests')
            .insert({
              title: analysisData.title || 'Конкурс',
              description: analysisData.description,
              prizes: analysisData.prizes || [],
              conditions: analysisData.conditions || [],
              channels: analysisData.channels || [],
              source_text: text,
              confidence_score: analysisData.confidence,
              end_date: analysisData.date ? new Date(analysisData.date).toISOString() : null,
              status: 'active'
            })
            .select()
            .single();

          if (insertError) {
            console.error('Ошибка сохранения конкурса:', insertError);
          }

          // Отправляем информацию о распознанном конкурсе
          const keyboard = {
            inline_keyboard: [[
              { text: '🎯 Участвовать', callback_data: `participate_${contest?.id}` }
            ]]
          };

          let responseText = `✅ <b>Конкурс распознан!</b>\n\n`;
          responseText += `🎯 ${analysisData.title}\n`;
          responseText += `📊 Уверенность: ${analysisData.confidence}%\n\n`;
          
          if (analysisData.prizes && analysisData.prizes.length > 0) {
            responseText += `🏆 Призы:\n${analysisData.prizes.map((p: string) => `  • ${p}`).join('\n')}\n\n`;
          }
          
          if (analysisData.conditions && analysisData.conditions.length > 0) {
            responseText += `📋 Условия:\n${analysisData.conditions.map((c: string) => `  • ${c}`).join('\n')}\n\n`;
          }

          await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              chat_id: chatId,
              text: responseText,
              parse_mode: 'HTML',
              reply_markup: keyboard
            })
          });
        } else {
          await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              chat_id: chatId,
              text: '❌ Не похоже на конкурс. Попробуйте переслать сообщение с конкурсом.',
              parse_mode: 'HTML'
            })
          });
        }
      } catch (error) {
        console.error('Ошибка анализа:', error);
        await fetch(`https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            chat_id: chatId,
            text: '⚠️ Произошла ошибка при анализе сообщения. Попробуйте позже.',
            parse_mode: 'HTML'
          })
        });
      }
    }

    return new Response(JSON.stringify({ ok: true }), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });

  } catch (error) {
    console.error('Ошибка webhook:', error);
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    return new Response(JSON.stringify({ error: errorMessage }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    });
  }
});
