do $$
begin
  if not exists (select from pg_roles where rolname = 'unmc_rag_app') then
    create role unmc_rag_app nologin;
  end if;
end
$$;

grant connect on database postgres to unmc_rag_app;
grant usage on schema rag to unmc_rag_app;
grant all on all tables in schema rag to unmc_rag_app;
grant all on all sequences in schema rag to unmc_rag_app;
alter default privileges in schema rag grant all on tables to unmc_rag_app;
alter default privileges in schema rag grant all on sequences to unmc_rag_app;

drop policy if exists app_all_document_chunks on rag.document_chunks;
create policy app_all_document_chunks
  on rag.document_chunks
  for all
  to unmc_rag_app
  using (true)
  with check (true);

drop policy if exists app_all_audit_events on rag.audit_events;
create policy app_all_audit_events
  on rag.audit_events
  for all
  to unmc_rag_app
  using (true)
  with check (true);
