import { useEffect } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "@/components/ui/toaster";
import Index from "@/pages/Index";
import Contests from "@/pages/Contests";
import Profile from "@/pages/Profile";

function App() {
  useEffect(() => {
    // Инициализация Telegram WebApp
    if (window.Telegram?.WebApp) {
      const tg = window.Telegram.WebApp;
      tg.ready();
      tg.expand();
      
      // Применяем тему Telegram
      document.documentElement.style.setProperty(
        '--tg-theme-bg-color',
        tg.themeParams.bg_color || '#0f1419'
      );
    }
  }, []);

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Index />} />
        <Route path="/contests" element={<Contests />} />
        <Route path="/profile" element={<Profile />} />
      </Routes>
      <Toaster />
    </BrowserRouter>
  );
}

export default App;
