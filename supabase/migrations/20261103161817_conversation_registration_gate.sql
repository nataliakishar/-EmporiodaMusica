-- A entrada do chat consulta os dois contatos em conjunto, sem abrir leitura de PII.
create schema emporio_registration_private;
revoke all on schema emporio_registration_private from public, anon, authenticated;
grant usage on schema emporio_registration_private to service_role;

create index customer_registrations_phone_email_idx on public.customer_registrations (phone, email);

create function emporio_registration_private.resolve_contacts(p_id uuid, p_name text, p_phone text, p_email text)
returns table(is_existing boolean, submission_id uuid)
language plpgsql security definer set search_path = ''
as $$
begin
    if p_id is null or p_name is null or p_phone is null or p_email is null
       or pg_catalog.char_length(p_name) not between 2 and 120 or p_name <> pg_catalog.btrim(p_name)
       or p_name ~ '[[:cntrl:]]' or p_phone !~ '^\+55[1-9][0-9][2-9][0-9]{7,8}$'
       or pg_catalog.char_length(p_email) not between 3 and 254 or p_email <> pg_catalog.lower(p_email)
       or p_email !~ '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$' then
        raise exception 'Invalid registration fields' using errcode = '22023';
    end if;
    perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(p_phone || E'\n' || p_email, 0));
    if exists(select 1 from public.customer_registrations r where r.id=p_id) then
        if not exists(select 1 from public.customer_registrations r
                      where r.id=p_id and r.name=p_name and r.phone=p_phone and r.email=p_email) then
            raise exception 'Submission conflict' using errcode = '22023';
        end if;
        return query select false, p_id;
    elsif exists(select 1 from public.customer_registrations r where r.phone=p_phone and r.email=p_email) then
        return query select true, null::uuid;
    else
        insert into public.customer_registrations (id,name,phone,email) values (p_id,p_name,p_phone,p_email);
        return query select false, p_id;
    end if;
end;
$$;
revoke all on function emporio_registration_private.resolve_contacts(uuid,text,text,text) from public, anon, authenticated;
grant execute on function emporio_registration_private.resolve_contacts(uuid,text,text,text) to service_role;

create function public.resolve_customer_registration(p_id uuid, p_name text, p_phone text, p_email text)
returns table(is_existing boolean, submission_id uuid)
language sql security invoker set search_path = ''
as $$ select * from emporio_registration_private.resolve_contacts(p_id,p_name,p_phone,p_email); $$;
revoke all on function public.resolve_customer_registration(uuid,text,text,text) from public, anon, authenticated;
grant execute on function public.resolve_customer_registration(uuid,text,text,text) to service_role;
