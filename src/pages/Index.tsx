import { useEffect, useState } from "react";
import { Gift, TrendingUp, Users } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import BottomNav from "@/components/BottomNav";

const Index = () => {
  const [userName, setUserName] = useState("Пользователь");

  useEffect(() => {
    if (window.Telegram?.WebApp) {
      const user = window.Telegram.WebApp.initDataUnsafe.user;
      if (user?.first_name) {
        setUserName(user.first_name);
      }
    }
  }, []);

  const stats = [
    { icon: Gift, label: "Активных конкурсов", value: "12", color: "text-primary" },
    { icon: TrendingUp, label: "Побед", value: "3", color: "text-green-500" },
    { icon: Users, label: "Участий", value: "45", color: "text-blue-500" },
  ];

  return (
    <div className="min-h-screen bg-background pb-20">
      <div className="container mx-auto px-4 py-6">
        {/* Приветствие */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold mb-2">
            Привет, {userName}! 👋
          </h1>
          <p className="text-muted-foreground">
            Твой AI-помощник в поиске призов
          </p>
        </div>

        {/* Статистика */}
        <div className="grid grid-cols-3 gap-3 mb-8">
          {stats.map((stat) => {
            const Icon = stat.icon;
            return (
              <Card key={stat.label} className="text-center">
                <CardContent className="pt-6 pb-4">
                  <Icon className={cn("w-8 h-8 mx-auto mb-2", stat.color)} />
                  <p className="text-2xl font-bold mb-1">{stat.value}</p>
                  <p className="text-xs text-muted-foreground leading-tight">
                    {stat.label}
                  </p>
                </CardContent>
              </Card>
            );
          })}
        </div>

        {/* Последние конкурсы */}
        <div className="mb-6">
          <h2 className="text-xl font-semibold mb-4">Новые конкурсы</h2>
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <Card key={i} className="hover:bg-muted/50 transition-colors">
                <CardHeader className="pb-3">
                  <CardTitle className="text-lg">Розыгрыш iPhone 16 Pro</CardTitle>
                  <CardDescription>
                    Завершится через 2 дня • Подписаться на 3 канала
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-muted-foreground">
                      Приз: 120 000 ₽
                    </span>
                    <Button size="sm">Участвовать</Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        {/* Quick Actions */}
        <div className="grid grid-cols-2 gap-3">
          <Button variant="outline" className="h-20 flex flex-col gap-2">
            <Gift className="w-6 h-6" />
            <span className="text-sm">Добавить конкурс</span>
          </Button>
          <Button variant="outline" className="h-20 flex flex-col gap-2">
            <TrendingUp className="w-6 h-6" />
            <span className="text-sm">Аналитика</span>
          </Button>
        </div>
      </div>

      <BottomNav />
    </div>
  );
};

export default Index;

function cn(...args: any[]) {
  return args.filter(Boolean).join(" ");
}
