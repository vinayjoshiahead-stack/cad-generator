create extension if not exists pgcrypto;

create table if not exists public.projects (
    id uuid primary key default gen_random_uuid(),
    user_id uuid references auth.users(id) on delete cascade,
    title text not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.model_generations (
    id uuid primary key default gen_random_uuid(),
    project_id uuid not null references public.projects(id) on delete cascade,
    parent_generation_id uuid references public.model_generations(id) on delete set null,
    user_prompt text not null default '',
    cad_query_code text not null default '',
    execution_status text not null check (execution_status in ('pending', 'completed', 'failed')),
    error_log text,
    gltf_url text,
    step_url text,
    stl_url text,
    svg_blueprint_url text,
    version_number integer not null check (version_number > 0),
    created_at timestamptz not null default now()
);

create index if not exists projects_user_id_idx on public.projects(user_id);
create index if not exists model_generations_project_id_idx on public.model_generations(project_id);
create index if not exists model_generations_parent_id_idx on public.model_generations(parent_generation_id);
create index if not exists model_generations_timeline_idx
    on public.model_generations(project_id, version_number, created_at);

insert into storage.buckets (id, name, public)
values ('cad-artifacts', 'cad-artifacts', true)
on conflict (id) do update set public = excluded.public;

drop policy if exists "Public can read CAD artifacts" on storage.objects;
create policy "Public can read CAD artifacts"
on storage.objects for select
using (bucket_id = 'cad-artifacts');

drop policy if exists "API clients can upload CAD artifacts" on storage.objects;
create policy "API clients can upload CAD artifacts"
on storage.objects for insert to anon, authenticated
with check (bucket_id = 'cad-artifacts');

drop policy if exists "API clients can update CAD artifacts" on storage.objects;
create policy "API clients can update CAD artifacts"
on storage.objects for update to anon, authenticated
using (bucket_id = 'cad-artifacts')
with check (bucket_id = 'cad-artifacts');

drop policy if exists "API clients can delete CAD artifacts" on storage.objects;
create policy "API clients can delete CAD artifacts"
on storage.objects for delete to anon, authenticated
using (bucket_id = 'cad-artifacts');