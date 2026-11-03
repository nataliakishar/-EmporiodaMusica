-- Cadastro novo e independente dos CSVs. Contatos não autenticam pedidos.
create table public.customer_registrations (
    id uuid primary key,
    name text not null check (char_length(name) between 2 and 120 and name = btrim(name) and name !~ '[[:cntrl:]]'),
    phone text not null check (phone ~ '^\+55[1-9][0-9][2-9][0-9]{7,8}$'),
    email text not null check (char_length(email) between 3 and 254 and email = lower(email) and email ~ '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$'),
    created_at timestamptz not null default now()
);

alter table public.customer_registrations enable row level security;
revoke all on table public.customer_registrations from public, anon, authenticated, service_role;
grant usage on schema public to service_role;
grant insert (id, name, phone, email) on public.customer_registrations to service_role;
grant select (id) on public.customer_registrations to service_role;

comment on table public.customer_registrations is 'Cadastro mínimo confirmado pelo cliente. Acesso somente pelo backend; não autentica pedidos.';
comment on column public.customer_registrations.id is 'UUID da submissão, reutilizado em repetições da mesma gravação.';
comment on column public.customer_registrations.email is 'Pode ser compartilhado por clientes diferentes; não é único nem prova de identidade.';
