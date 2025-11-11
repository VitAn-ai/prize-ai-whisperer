import { useEffect, useState } from "react";
import { BottomNav } from "@/components/BottomNav";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { supabase } from "@/integrations/supabase/client";
import { useToast } from "@/hooks/use-toast";

interface Contest {
  id: string;
  title: string;
  description: string;
  prizes: string[];
  confidence_score: number;
  end_date: string;
  created_at: string;
}

const Index = () => {
  const [contests, setContests] = useState<Contest[]>([]);
  const [loading, setLoading] = useState(true);
  const { toast } = useToast();

  useEffect(() => {
    fetchContests();
    
    // Подписываемся на новые конкурсы в реальном времени
    const channel = supabase
      .channel('contests-changes')
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'contests'
        },
        (payload) => {
          console.log('Новый конкурс:', payload);
          setContests(prev => [payload.new as Contest, ...prev]);
          toast({
            title: "🎁 Новый конкурс!",
            description: (payload.new as Contest).title,
          });
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, []);

  const fetchContests = async () => {
    try {
      const { data, error } = await supabase
        .from('contests')
        .select('*')
        .eq('status', 'active')
        .order('created_at', { ascending: false })
        .limit(20);

      if (error) throw error;
      setContests(data || []);
    } catch (error) {
      console.error('Ошибка загрузки конкурсов:', error);
      toast({
        title: "Ошибка",
        description: "Не удалось загрузить конкурсы",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const openTelegram = () => {
    window.open('https://t.me/YOUR_BOT_USERNAME', '_blank');
  };

  return (
    <div className="min-h-screen bg-background pb-20">
      <div className="container mx-auto px-4 py-8">
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-foreground mb-2">
            Prize AI Whisperer
          </h1>
          <p className="text-muted-foreground text-lg mb-4">
            Умный помощник для участия в конкурсах Telegram
          </p>
          <Button onClick={openTelegram} size="lg" className="w-full sm:w-auto">
            🤖 Открыть бота в Telegram
          </Button>
        </div>

        <div className="mb-6">
          <h2 className="text-2xl font-semibold text-foreground mb-4">
            Активные конкурсы
          </h2>
          {loading ? (
            <div className="text-center py-8">
              <p className="text-muted-foreground">Загрузка конкурсов...</p>
            </div>
          ) : contests.length === 0 ? (
            <Card>
              <CardContent className="py-8 text-center">
                <p className="text-muted-foreground">
                  Пока нет активных конкурсов. Пересылайте сообщения с конкурсами боту в Telegram!
                </p>
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-4">
              {contests.map((contest) => (
                <Card key={contest.id}>
                  <CardHeader>
                    <CardTitle className="flex items-start justify-between">
                      <span>{contest.title}</span>
                      <span className="text-sm font-normal bg-primary/10 text-primary px-2 py-1 rounded">
                        {contest.confidence_score}%
                      </span>
                    </CardTitle>
                    {contest.description && (
                      <CardDescription>{contest.description}</CardDescription>
                    )}
                  </CardHeader>
                  <CardContent>
                    {contest.prizes && contest.prizes.length > 0 && (
                      <div className="mb-3">
                        <p className="text-sm font-semibold mb-1">🏆 Призы:</p>
                        <ul className="list-disc list-inside text-sm text-muted-foreground">
                          {contest.prizes.map((prize, idx) => (
                            <li key={idx}>{prize}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {contest.end_date && (
                      <p className="text-sm text-muted-foreground mb-3">
                        ⏰ До: {new Date(contest.end_date).toLocaleDateString('ru-RU')}
                      </p>
                    )}
                    <Button onClick={openTelegram} className="w-full">
                      Участвовать
                    </Button>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>
      </div>
      <BottomNav />
    </div>
  );
};

export default Index;
