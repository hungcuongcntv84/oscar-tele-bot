-- Run once in Supabase SQL Editor. Never commit credentials.
create table if not exists public.groups (
 chat_id bigint primary key, title text not null, active boolean not null default true
);
create table if not exists public.messages (
 chat_id bigint not null, message_id bigint not null,
 title text not null, sender text not null, sent_at timestamptz not null, body text not null,
 primary key(chat_id,message_id)
);
create index if not exists messages_sent_at_idx on public.messages(sent_at);
create table if not exists public.report_state (
 key text primary key, value text not null
);
alter table public.groups enable row level security;
alter table public.messages enable row level security;
alter table public.report_state enable row level security;
-- No public policies: only service role (backend) may access.
