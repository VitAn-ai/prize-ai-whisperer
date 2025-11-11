import { useEffect, useState } from "react";
import { Settings, Bell, Award, TrendingUp, LogOut } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import BottomNav from "@/components/BottomNav";

const Profile = () => {
  const [user, setUser] = useState({
    firstName: "Пользователь",
    username: "",
  });

  useEffect(() => {
    if (window.Telegram?.WebApp) {
      const tgUser = window.Telegram.WebApp.initDataUnsafe.user;
      if (tgUser) {
        setUser({
          firstName: tgUser.first_name || "Пользователь",
          username: tgUser.username || "",
        });
      }
    }
  }, []);

  const achievements = [
    { icon: Award, title: "Первая победа", description: "Выиграл первый конкурс" },
    { icon: TrendingUp, title: "Активный участник", description: "Участвовал в 50+ конкурсах" },
  ];

  const menuItems = [
    { icon: Bell, title: "Уведомления", description: "Настройки уведомлений" },
    { icon: Settings, title: "Настройки", description: "Общие настройки" },
  ];

  return (
    <div className="min-h-screen bg-background pb-20">
      <div className="container mx-auto px-4 py-6">
        {/* Профиль пользователя */}
        <Card className="mb-6">
          <CardHeader className="text-center pb-4">
            <div className="w-20 h-20 bg-primary rounded-full mx-auto mb-4 flex items-center justify-center text-3xl font-bold">
              {user.firstName[0]}
            </div>
            <CardTitle className="text-2xl">{user.firstName}</CardTitle>
            {user.username && (
              <CardDescription>@{user.username}</CardDescription>
            )}
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-4 text-center">
              <div>
                <p className="text-2xl font-bold text-primary">12</p>
                <p className="text-xs text-muted-foreground">Активных</p>
              </div>
              <div>
                <p className="text-2xl font-bold text-green-500">3</p>
                <p className="text-xs text-muted-foreground">Побед</p>
              </div>
              <div>
                <p className="text-2xl font-bold text-blue-500">45</p>
                <p className="text-xs text-muted-foreground">Участий</p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Достижения */}
        <div className="mb-6">
          <h2 className="text-xl font-semibold mb-4">Достижения</h2>
          <div className="grid grid-cols-2 gap-3">
            {achievements.map((achievement) => {
              const Icon = achievement.icon;
              return (
                <Card key={achievement.title} className="text-center">
                  <CardContent className="pt-6 pb-4">
                    <Icon className="w-8 h-8 mx-auto mb-2 text-primary" />
                    <p className="text-sm font-semibold mb-1">{achievement.title}</p>
                    <p className="text-xs text-muted-foreground leading-tight">
                      {achievement.description}
                    </p>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </div>

        {/* Меню настроек */}
        <div className="space-y-2 mb-6">
          {menuItems.map((item) => {
            const Icon = item.icon;
            return (
              <Card key={item.title} className="hover:bg-muted/50 transition-colors cursor-pointer">
                <CardHeader className="py-4">
                  <div className="flex items-center gap-3">
                    <Icon className="w-5 h-5 text-primary" />
                    <div>
                      <CardTitle className="text-base">{item.title}</CardTitle>
                      <CardDescription className="text-xs">
                        {item.description}
                      </CardDescription>
                    </div>
                  </div>
                </CardHeader>
              </Card>
            );
          })}
        </div>

        {/* Выход */}
        <Button variant="destructive" className="w-full" size="lg">
          <LogOut className="w-4 h-4 mr-2" />
          Выйти
        </Button>
      </div>

      <BottomNav />
    </div>
  );
};

export default Profile;
