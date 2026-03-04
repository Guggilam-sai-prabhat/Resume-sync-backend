create table if not exists public.resumes (
  id          uuid primary key default gen_random_uuid(),
  title       text        not null,
  full_name   text        not null,
  email       text        not null,
  phone       text,
  summary     text,
  experience  jsonb       not null default '[]'::jsonb,
  education   jsonb       not null default '[]'::jsonb,
  skills      jsonb       not null default '[]'::jsonb,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create or replace function public.set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create trigger resumes_set_updated_at
  before update on public.resumes
  for each row execute function public.set_updated_at();
