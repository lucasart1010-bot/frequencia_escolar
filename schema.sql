-- Data Mart de frequência escolar (Supabase / PostgreSQL)
-- Rode no Supabase: SQL Editor > New query > colar > Run

create table if not exists alunos (
  id            bigint generated always as identity primary key,
  nome          text   not null,
  turma         text   not null default 'Turma A',
  data_entrada  date   not null default current_date,
  contato       text                       -- só dígitos, com DDD (ex.: 91982748035)
);

-- Se a tabela alunos já existia sem o contato, rode também:
-- alter table alunos add column if not exists contato text;

create table if not exists frequencias (
  id          bigint generated always as identity primary key,
  aluno_id    bigint not null references alunos(id) on delete cascade,
  data        date   not null,
  status      text   not null check (status in ('presente', 'falta', 'justificada')),
  observacao  text,
  unique (aluno_id, data)            -- 1 registro por aluno por dia (permite regravar o dia)
);

create index if not exists idx_freq_data  on frequencias (data);
create index if not exists idx_freq_aluno on frequencias (aluno_id);

-- Segurança: bloqueia acesso público direto às tabelas.
-- O app (servidor) usa a chave service_role, que ignora o RLS.
alter table alunos       enable row level security;
alter table frequencias  enable row level security;

-- Lista da turma: rode o seed_alunos.sql (ou use "Importar" na aba Alunos do app).
