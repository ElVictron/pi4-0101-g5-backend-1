-- Dados de exemplo para a demonstração (card #802): 4 livros, 3 usuários e 3
-- empréstimos, um deles ATRASADO (data limite há 5 dias, ainda sem devolução).
-- Só insere se o banco estiver vazio. Uso (com o Compose de pé):
--   docker compose exec -T postgres psql -U biblioteca -d biblioteca < db/dados-demo.sql
-- As datas são relativas a "agora" (horário de America/Sao_Paulo, sem fração).

DO $$
DECLARE
    agora timestamp(0) := date_trunc('second', now() AT TIME ZONE 'America/Sao_Paulo');
    dom_casmurro integer;
    cortico integer;
    ana integer;
    bruno integer;
    carla integer;
BEGIN
    IF EXISTS (SELECT 1 FROM livros) OR EXISTS (SELECT 1 FROM usuarios) THEN
        RAISE NOTICE 'Banco já tem dados; nada foi inserido.';
        RETURN;
    END IF;

    -- Disponibilidade já considera os empréstimos ativos abaixo.
    INSERT INTO livros (titulo, autor, isbn, quantidade_exemplares, quantidade_disponivel)
    VALUES ('Dom Casmurro', 'Machado de Assis', '9780000000001', 3, 1)
    RETURNING id INTO dom_casmurro;
    INSERT INTO livros (titulo, autor, isbn, quantidade_exemplares, quantidade_disponivel)
    VALUES ('O Cortiço', 'Aluísio Azevedo', '9780000000002', 2, 2)
    RETURNING id INTO cortico;
    INSERT INTO livros (titulo, autor, isbn, quantidade_exemplares, quantidade_disponivel)
    VALUES ('Memórias Póstumas de Brás Cubas', 'Machado de Assis', '9780000000003', 1, 1),
           ('Capitães da Areia', 'Jorge Amado', '9780000000004', 4, 4);

    INSERT INTO usuarios (nome, cpf, contato)
    VALUES ('Ana Souza', '52998224725', 'ana.souza@exemplo.com')
    RETURNING id INTO ana;
    INSERT INTO usuarios (nome, cpf, contato)
    VALUES ('Bruno Lima', '11144477735', 'bruno.lima@exemplo.com')
    RETURNING id INTO bruno;
    INSERT INTO usuarios (nome, cpf, contato)
    VALUES ('Carla Dias', '39053344705', 'carla.dias@exemplo.com')
    RETURNING id INTO carla;

    -- Atrasado: emprestado há 20 dias, prazo de 15 dias venceu há 5, sem devolução.
    INSERT INTO emprestimos (usuario_id, livro_id, status, emprestado_em, data_limite_devolucao)
    VALUES (ana, dom_casmurro, 'ativo', agora - interval '20 days', agora - interval '5 days');
    -- Ativo no prazo.
    INSERT INTO emprestimos (usuario_id, livro_id, status, emprestado_em, data_limite_devolucao)
    VALUES (bruno, dom_casmurro, 'ativo', agora - interval '2 days', agora + interval '13 days');
    -- Já devolvido.
    INSERT INTO emprestimos (usuario_id, livro_id, status, emprestado_em, data_limite_devolucao, devolvido_em)
    VALUES (carla, cortico, 'devolvido', agora - interval '10 days', agora + interval '5 days', agora - interval '3 days');
END
$$;
