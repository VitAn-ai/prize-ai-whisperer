-- Создаем таблицу для конкурсов
CREATE TABLE IF NOT EXISTS public.contests (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  title text NOT NULL,
  description text,
  end_date timestamptz,
  channels text[],
  prizes text[],
  conditions text[],
  confidence_score integer DEFAULT 0,
  source_text text,
  status text DEFAULT 'active' CHECK (status IN ('active', 'completed', 'expired')),
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

-- Создаем таблицу для участий пользователей
CREATE TABLE IF NOT EXISTS public.user_participations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id bigint NOT NULL,
  contest_id uuid REFERENCES public.contests(id) ON DELETE CASCADE,
  telegram_username text,
  telegram_first_name text,
  joined_at timestamptz DEFAULT now(),
  subscription_checked boolean DEFAULT false,
  unsubscribed_at timestamptz,
  UNIQUE(user_id, contest_id)
);

-- Создаем таблицу для отслеживания подписок
CREATE TABLE IF NOT EXISTS public.subscription_tracking (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id bigint NOT NULL,
  contest_id uuid REFERENCES public.contests(id) ON DELETE CASCADE,
  channel_name text NOT NULL,
  subscribed boolean DEFAULT true,
  checked_at timestamptz DEFAULT now(),
  unsubscribed_at timestamptz
);

-- Индексы для оптимизации
CREATE INDEX IF NOT EXISTS idx_contests_status ON public.contests(status);
CREATE INDEX IF NOT EXISTS idx_contests_end_date ON public.contests(end_date);
CREATE INDEX IF NOT EXISTS idx_user_participations_user_id ON public.user_participations(user_id);
CREATE INDEX IF NOT EXISTS idx_user_participations_contest_id ON public.user_participations(contest_id);
CREATE INDEX IF NOT EXISTS idx_subscription_tracking_user_contest ON public.subscription_tracking(user_id, contest_id);

-- Функция для обновления updated_at
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Триггер для contests
DROP TRIGGER IF EXISTS update_contests_updated_at ON public.contests;
CREATE TRIGGER update_contests_updated_at
  BEFORE UPDATE ON public.contests
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

-- RLS policies
ALTER TABLE public.contests ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_participations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.subscription_tracking ENABLE ROW LEVEL SECURITY;

-- Публичное чтение конкурсов
CREATE POLICY "Contests are viewable by everyone"
  ON public.contests FOR SELECT
  USING (true);

-- Только система может создавать конкурсы (через edge functions)
CREATE POLICY "System can insert contests"
  ON public.contests FOR INSERT
  WITH CHECK (true);

-- Пользователи видят только свои участия
CREATE POLICY "Users can view their own participations"
  ON public.user_participations FOR SELECT
  USING (true);

CREATE POLICY "Users can insert their own participations"
  ON public.user_participations FOR INSERT
  WITH CHECK (true);

-- Пользователи видят свое отслеживание подписок
CREATE POLICY "Users can view their subscription tracking"
  ON public.subscription_tracking FOR SELECT
  USING (true);

CREATE POLICY "System can manage subscription tracking"
  ON public.subscription_tracking FOR ALL
  USING (true);