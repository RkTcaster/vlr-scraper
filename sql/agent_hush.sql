-- Hush (patch 13.09, aparece en el Europe Qualifier). agent_info NO la sube el pipeline
-- (table_agent_info.csv se genera pero no esta en FILES_TO_UPLOAD), asi que cada agente nuevo
-- se agrega a mano. Idempotente.
insert into public.agent_info (agent_name, agent_path)
select 'Hush', 'agents/hush.png'
where not exists (select 1 from public.agent_info where agent_name = 'Hush');
