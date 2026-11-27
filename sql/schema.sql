-- SDLC Platform

-- משתמשים: user_id הוא המזהה הפנימי; email ו-username ייחודיים
create table if not exists public.users (
    user_id uuid primary key,
    first_name text not null,
    last_name text not null,
    email text not null unique,
    username text not null unique,
    created_at timestamptz not null default now()
);

alter table public.users enable row level security;

grant select, insert on public.users to service_role;

-- ריפוזיטוריז: משויכים למשתמש דרך user_id
create table if not exists public.repositories (
    id bigint generated always as identity primary key,
    user_id uuid not null references public.users (user_id),
    github_user text not null,
    github_password_encrypted text not null,
    repo_url text not null,
    created_at timestamptz not null default now()
);

-- RLS פעיל בלי policies: רק ה-service role (השרת) יכול לקרוא/לכתוב
alter table public.repositories enable row level security;

-- הרשאות לשרת (פרויקטים חדשים ב-Supabase לא נותנים אותן אוטומטית)
grant select, insert on public.repositories to service_role;

-- פיצ'רים: username + repo + feature_id הם יחד ה-primary key.
-- feature_id (UUID) משמש לתיקייה .platform/{feature_id}/
create table if not exists public.features (
    username text not null,
    repo_url text not null,
    feature_id uuid not null,
    created_at timestamptz not null default now(),
    primary key (username, repo_url, feature_id)
);

alter table public.features enable row level security;

grant select, insert on public.features to service_role;

-- משימות: שייכות לפיצ'ר (foreign key על שלושת שדות המפתח של features)
create table if not exists public.tasks (
    username text not null,
    repo_url text not null,
    feature_id uuid not null,
    task_id uuid not null,
    created_at timestamptz not null default now(),
    primary key (username, repo_url, feature_id, task_id),
    foreign key (username, repo_url, feature_id)
        references public.features (username, repo_url, feature_id)
);

alter table public.tasks enable row level security;

grant select, insert on public.tasks to service_role;
