-- Estado do atendimento e fontes do backend. Nada acessível a anon/authenticated.
create schema emporio_agent_private;
revoke all on schema emporio_agent_private from public, anon, authenticated;
grant usage on schema emporio_agent_private to service_role;

create table emporio_agent_private.sessions (
    id uuid primary key,
    token_hash text not null check (token_hash ~ '^[0-9a-f]{64}$'),
    state jsonb not null default '{}'::jsonb,
    expires_at timestamptz not null default now() + interval '30 minutes',
    lease uuid,
    lease_until timestamptz
);
create index agent_sessions_expiry_idx on emporio_agent_private.sessions(expires_at);
alter table emporio_agent_private.sessions enable row level security;
revoke all on emporio_agent_private.sessions from public, anon, authenticated;
grant select, insert, update, delete on emporio_agent_private.sessions to service_role;

create table emporio_agent_private.assets (
    singleton boolean primary key default true check(singleton),
    bundle jsonb not null check (pg_catalog.octet_length(bundle::text) < 1000000)
);
alter table emporio_agent_private.assets enable row level security;
revoke all on emporio_agent_private.assets from public, anon, authenticated;
grant select, insert, update on emporio_agent_private.assets to service_role;

create function public.agent_session_create(p_id uuid, p_hash text)
returns jsonb language plpgsql security invoker set search_path = '' as $$
begin
    perform pg_catalog.pg_advisory_xact_lock(617438267);
    delete from emporio_agent_private.sessions where expires_at <= now()
      and (lease_until is null or lease_until <= now());
    if (select count(*) from emporio_agent_private.sessions) >= 100 then
        return pg_catalog.jsonb_build_object('code','capacity');
    end if;
    insert into emporio_agent_private.sessions(id,token_hash) values(p_id,p_hash);
    return pg_catalog.jsonb_build_object('code','created');
end $$;

create function public.agent_session_acquire(p_id uuid, p_hash text, p_lease uuid)
returns jsonb language plpgsql security invoker set search_path = '' as $$
declare current_row emporio_agent_private.sessions%rowtype;
begin
    select * into current_row from emporio_agent_private.sessions where id=p_id for update;
    if not found or current_row.token_hash <> p_hash then
        return pg_catalog.jsonb_build_object('code','not_found');
    end if;
    if current_row.lease_until > now() then
        return pg_catalog.jsonb_build_object('code','busy');
    end if;
    if current_row.expires_at <= now() then
        delete from emporio_agent_private.sessions where id=p_id;
        return pg_catalog.jsonb_build_object('code','not_found');
    end if;
    update emporio_agent_private.sessions set lease=p_lease,
      lease_until=now()+interval '330 seconds' where id=p_id;
    return pg_catalog.jsonb_build_object('code','acquired','state',current_row.state);
end $$;

create function public.agent_session_finish(p_id uuid, p_lease uuid, p_state jsonb, p_close boolean)
returns boolean language plpgsql security invoker set search_path = '' as $$
begin
    if p_close then
        delete from emporio_agent_private.sessions where id=p_id and lease=p_lease;
    else
        if pg_catalog.jsonb_typeof(p_state) <> 'object' or pg_catalog.octet_length(p_state::text)>262144 then
            raise exception 'Invalid session state' using errcode='22023';
        end if;
        update emporio_agent_private.sessions set state=p_state,
          expires_at=now()+interval '30 minutes',lease=null,lease_until=null
          where id=p_id and lease=p_lease;
    end if;
    return found;
end $$;

create function public.agent_assets_set(p_bundle jsonb)
returns boolean language plpgsql security invoker set search_path = '' as $$
begin
    if pg_catalog.jsonb_typeof(p_bundle->'files') <> 'object' then
        raise exception 'Invalid source bundle' using errcode='22023';
    end if;
    insert into emporio_agent_private.assets(singleton,bundle) values(true,p_bundle)
      on conflict(singleton) do update set bundle=excluded.bundle;
    return true;
end $$;

create function public.agent_assets_get()
returns jsonb language sql stable security invoker set search_path = '' as $$
    select bundle from emporio_agent_private.assets where singleton=true;
$$;

revoke all on function public.agent_session_create(uuid,text) from public, anon, authenticated;
revoke all on function public.agent_session_acquire(uuid,text,uuid) from public, anon, authenticated;
revoke all on function public.agent_session_finish(uuid,uuid,jsonb,boolean) from public, anon, authenticated;
revoke all on function public.agent_assets_set(jsonb) from public, anon, authenticated;
revoke all on function public.agent_assets_get() from public, anon, authenticated;
grant execute on function public.agent_session_create(uuid,text) to service_role;
grant execute on function public.agent_session_acquire(uuid,text,uuid) to service_role;
grant execute on function public.agent_session_finish(uuid,uuid,jsonb,boolean) to service_role;
grant execute on function public.agent_assets_set(jsonb) to service_role;
grant execute on function public.agent_assets_get() to service_role;
