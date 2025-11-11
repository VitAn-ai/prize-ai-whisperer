import { useState } from "react";
import { Search, Filter, Calendar, Award } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import BottomNav from "@/components/BottomNav";

const Contests = () => {
  const [activeTab, setActiveTab] = useState("active");

  const contests = [
    {
      id: 1,
      title: "iPhone 16 Pro Max",
      prize: "120 000 ₽",
      endDate: "через 2 дня",
      requirements: "3 канала",
      status: "active",
    },
    {
      id: 2,
      title: "MacBook Air M3",
      prize: "150 000 ₽",
      endDate: "через 5 дней",
      requirements: "5 каналов",
      status: "active",
    },
    {
      id: 3,
      title: "AirPods Pro",
      prize: "25 000 ₽",
      endDate: "через 1 день",
      requirements: "2 канала",
      status: "active",
    },
    {
      id: 4,
      title: "PlayStation 5",
      prize: "60 000 ₽",
      endDate: "завершён",
      requirements: "4 канала",
      status: "completed",
    },
  ];

  const activeContests = contests.filter(c => c.status === "active");
  const completedContests = contests.filter(c => c.status === "completed");

  return (
    <div className="min-h-screen bg-background pb-20">
      <div className="container mx-auto px-4 py-6">
        {/* Заголовок */}
        <div className="mb-6">
          <h1 className="text-3xl font-bold mb-2">Конкурсы</h1>
          <p className="text-muted-foreground">Найди свой приз</p>
        </div>

        {/* Поиск и фильтры */}
        <div className="flex gap-2 mb-6">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Поиск конкурсов..."
              className="w-full pl-10 pr-4 py-2 bg-muted rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>
          <Button variant="outline" size="icon">
            <Filter className="w-4 h-4" />
          </Button>
        </div>

        {/* Табы */}
        <Tabs defaultValue="active" value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="w-full mb-6">
            <TabsTrigger value="active" className="flex-1">
              Активные ({activeContests.length})
            </TabsTrigger>
            <TabsTrigger value="completed" className="flex-1">
              Завершённые ({completedContests.length})
            </TabsTrigger>
          </TabsList>

          <TabsContent value="active" className="space-y-3">
            {activeContests.map((contest) => (
              <Card key={contest.id} className="hover:bg-muted/50 transition-colors">
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between">
                    <div>
                      <CardTitle className="text-lg mb-1">{contest.title}</CardTitle>
                      <CardDescription className="flex items-center gap-1">
                        <Calendar className="w-3 h-3" />
                        {contest.endDate}
                      </CardDescription>
                    </div>
                    <Award className="w-6 h-6 text-primary" />
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="flex justify-between items-center mb-3">
                    <span className="text-sm text-muted-foreground">
                      Приз: <span className="font-semibold text-foreground">{contest.prize}</span>
                    </span>
                    <span className="text-xs bg-primary/10 text-primary px-2 py-1 rounded">
                      {contest.requirements}
                    </span>
                  </div>
                  <Button className="w-full">Участвовать</Button>
                </CardContent>
              </Card>
            ))}
          </TabsContent>

          <TabsContent value="completed" className="space-y-3">
            {completedContests.map((contest) => (
              <Card key={contest.id} className="opacity-60">
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between">
                    <div>
                      <CardTitle className="text-lg mb-1">{contest.title}</CardTitle>
                      <CardDescription className="flex items-center gap-1">
                        <Calendar className="w-3 h-3" />
                        {contest.endDate}
                      </CardDescription>
                    </div>
                    <Award className="w-6 h-6 text-muted-foreground" />
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-muted-foreground">
                      Приз: {contest.prize}
                    </span>
                    <Button variant="ghost" size="sm" disabled>
                      Завершён
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </TabsContent>
        </Tabs>
      </div>

      <BottomNav />
    </div>
  );
};

export default Contests;
