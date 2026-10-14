-- Run this complete file in your project's Supabase SQL Editor.
-- Only Meet Master objects are created; other project tables are untouched.
begin;

create table if not exists public.mm_profiles (
  user_id uuid primary key references auth.users(id) on delete cascade default auth.uid(),
  name text not null check (length(name) between 1 and 100),
  company text not null check (length(company) between 1 and 100)
);
create table if not exists public.mm_agents (
  id uuid primary key,
  owner_id uuid not null references auth.users(id) on delete cascade default auth.uid(),
  name text not null check (length(name) between 1 and 100),
  description text not null default '' check (length(description) <= 500),
  instructions text not null check (length(instructions) between 1 and 12000),
  tags jsonb not null default '[]'::jsonb check (jsonb_typeof(tags) = 'array'),
  created timestamptz not null default now(),
  unique (id, owner_id)
);
create table if not exists public.mm_meetings (
  id uuid primary key,
  owner_id uuid not null references auth.users(id) on delete cascade default auth.uid(),
  title text not null check (length(title) between 1 and 200),
  url text not null default '' check (length(url) <= 2048),
  platform text not null,
  agent_id uuid,
  status text not null,
  consent integer not null check (consent = 1),
  transcript text not null default '' check (length(transcript) <= 120000),
  notes jsonb not null default '{}'::jsonb check (jsonb_typeof(notes) = 'object'),
  bot_id text,
  created timestamptz not null default now(),
  consent_at timestamptz not null,
  error text not null default '',
  foreign key (agent_id, owner_id) references public.mm_agents(id, owner_id)
);
create index if not exists mm_agents_owner_created on public.mm_agents(owner_id, created desc);
create index if not exists mm_meetings_owner_created on public.mm_meetings(owner_id, created desc);
create index if not exists mm_meetings_agent on public.mm_meetings(agent_id, owner_id);

alter table public.mm_profiles enable row level security;
alter table public.mm_agents enable row level security;
alter table public.mm_meetings enable row level security;

drop policy if exists mm_profiles_owner on public.mm_profiles;
create policy mm_profiles_owner on public.mm_profiles for all to authenticated
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
drop policy if exists mm_agents_owner on public.mm_agents;
create policy mm_agents_owner on public.mm_agents for all to authenticated
  using (owner_id = (select auth.uid())) with check (owner_id = (select auth.uid()));
drop policy if exists mm_meetings_owner on public.mm_meetings;
create policy mm_meetings_owner on public.mm_meetings for all to authenticated
  using (owner_id = (select auth.uid())) with check (owner_id = (select auth.uid()));

revoke all on public.mm_profiles, public.mm_agents, public.mm_meetings from public, anon;
grant select, insert, update, delete on public.mm_profiles, public.mm_agents, public.mm_meetings to authenticated;

create or replace function public.mm_delete_agent(p_id uuid)
returns void language plpgsql security invoker set search_path = '' as $$
begin
  if auth.uid() is null then raise exception 'Authentication required'; end if;
  update public.mm_meetings set agent_id = null where agent_id = p_id and owner_id = auth.uid();
  delete from public.mm_agents where id = p_id and owner_id = auth.uid();
end;
$$;

-- Atomic one-time import. Refuses to overwrite an existing cloud workspace.
create or replace function public.mm_import_workspace(p_data jsonb)
returns jsonb language plpgsql security invoker set search_path = '' as $$
declare owner uuid := auth.uid();
begin
  if owner is null then raise exception 'Authentication required'; end if;
  perform pg_advisory_xact_lock(hashtextextended(owner::text, 0));
  if exists (select 1 from public.mm_agents where owner_id = owner)
     or exists (select 1 from public.mm_meetings where owner_id = owner)
     or exists (select 1 from public.mm_profiles where user_id = owner) then
    raise exception 'Cloud workspace already contains data. Import cancelled.';
  end if;
  insert into public.mm_profiles(user_id, name, company)
    values (owner, p_data->'profile'->>'name', p_data->'profile'->>'company');
  insert into public.mm_agents(id, owner_id, name, description, instructions, tags, created)
    select a.id, owner, a.name, a.description, a.instructions, a.tags, a.created
    from jsonb_to_recordset(p_data->'agents') as a(id uuid, name text, description text,
      instructions text, tags jsonb, created timestamptz);
  insert into public.mm_meetings(id, owner_id, title, url, platform, agent_id, status,
      consent, transcript, notes, bot_id, created, consent_at, error)
    select m.id, owner, m.title, m.url, m.platform, m.agent_id, m.status,
      m.consent, m.transcript, m.notes, m.bot_id, m.created, m.consent_at, m.error
    from jsonb_to_recordset(p_data->'meetings') as m(id uuid, title text, url text,
      platform text, agent_id uuid, status text, consent integer, transcript text,
      notes jsonb, bot_id text, created timestamptz, consent_at timestamptz, error text);
  return jsonb_build_object('agents', jsonb_array_length(p_data->'agents'),
                           'meetings', jsonb_array_length(p_data->'meetings'));
end;
$$;
revoke all on function public.mm_delete_agent(uuid), public.mm_import_workspace(jsonb) from public, anon;
grant execute on function public.mm_delete_agent(uuid), public.mm_import_workspace(jsonb) to authenticated;
notify pgrst, 'reload schema';
commit;
