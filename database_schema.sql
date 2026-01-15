--
-- PostgreSQL database dump
--

\restrict lfpoIBtgK3B6FBTpgG1RuniNJGsKD1Sb6AfsDiO5juc0RjBhsBKzh7AD88mft6G

-- Dumped from database version 16.11 (Ubuntu 16.11-0ubuntu0.24.04.1)
-- Dumped by pg_dump version 16.11 (Ubuntu 16.11-0ubuntu0.24.04.1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: vector; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;


--
-- Name: EXTENSION vector; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION vector IS 'vector data type and ivfflat and hnsw access methods';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: law_amendments; Type: TABLE; Schema: public; Owner: flaskapp
--

CREATE TABLE public.law_amendments (
    id integer NOT NULL,
    law_id integer NOT NULL,
    consultant_id character varying(50) NOT NULL,
    fz_number character varying(50),
    fz_date date,
    title text,
    full_text text,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.law_amendments OWNER TO flaskapp;

--
-- Name: law_amendments_id_seq; Type: SEQUENCE; Schema: public; Owner: flaskapp
--

CREATE SEQUENCE public.law_amendments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.law_amendments_id_seq OWNER TO flaskapp;

--
-- Name: law_amendments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: flaskapp
--

ALTER SEQUENCE public.law_amendments_id_seq OWNED BY public.law_amendments.id;


--
-- Name: law_editions; Type: TABLE; Schema: public; Owner: flaskapp
--

CREATE TABLE public.law_editions (
    id integer NOT NULL,
    law_id integer NOT NULL,
    edition_id integer NOT NULL,
    rdk integer,
    valid_from date,
    valid_to date,
    change_reason text,
    content_html text,
    is_current boolean DEFAULT false,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.law_editions OWNER TO flaskapp;

--
-- Name: law_editions_id_seq; Type: SEQUENCE; Schema: public; Owner: flaskapp
--

CREATE SEQUENCE public.law_editions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.law_editions_id_seq OWNER TO flaskapp;

--
-- Name: law_editions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: flaskapp
--

ALTER SEQUENCE public.law_editions_id_seq OWNED BY public.law_editions.id;


--
-- Name: law_embeddings; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.law_embeddings (
    id integer NOT NULL,
    title text NOT NULL,
    authority text,
    eo_number text,
    search_text text,
    full_text text,
    embedding public.vector(1536),
    created_at timestamp without time zone DEFAULT now(),
    law_number character varying(50),
    law_date date,
    last_amendment_date date,
    last_amendment_info text,
    consultant_id character varying(20),
    consultant_url text
);


ALTER TABLE public.law_embeddings OWNER TO postgres;

--
-- Name: law_embeddings_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.law_embeddings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.law_embeddings_id_seq OWNER TO postgres;

--
-- Name: law_embeddings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.law_embeddings_id_seq OWNED BY public.law_embeddings.id;


--
-- Name: law_revisions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.law_revisions (
    id integer NOT NULL,
    law_id integer NOT NULL,
    revision_date date NOT NULL,
    revision_number character varying(50),
    revision_description text,
    full_text text,
    embedding public.vector(1536),
    consultant_url text,
    is_current boolean DEFAULT false,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.law_revisions OWNER TO postgres;

--
-- Name: TABLE law_revisions; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.law_revisions IS 'Таблица для хранения всех редакций законов';


--
-- Name: COLUMN law_revisions.law_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.law_revisions.law_id IS 'ID основного закона из law_embeddings';


--
-- Name: COLUMN law_revisions.revision_date; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.law_revisions.revision_date IS 'Дата редакции';


--
-- Name: COLUMN law_revisions.revision_number; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.law_revisions.revision_number IS 'Номер документа который внес изменения (например "565-ФЗ")';


--
-- Name: COLUMN law_revisions.revision_description; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.law_revisions.revision_description IS 'Описание редакции';


--
-- Name: COLUMN law_revisions.consultant_url; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.law_revisions.consultant_url IS 'Ссылка на эту редакцию на Консультант Плюс';


--
-- Name: COLUMN law_revisions.is_current; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.law_revisions.is_current IS 'Флаг актуальной (последней) редакции';


--
-- Name: law_revisions_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.law_revisions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.law_revisions_id_seq OWNER TO postgres;

--
-- Name: law_revisions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.law_revisions_id_seq OWNED BY public.law_revisions.id;


--
-- Name: legal_regimes; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.legal_regimes (
    id integer NOT NULL,
    name text NOT NULL,
    category character varying(50) NOT NULL,
    description text,
    parent_regime_id integer
);


ALTER TABLE public.legal_regimes OWNER TO postgres;

--
-- Name: legal_regimes_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.legal_regimes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.legal_regimes_id_seq OWNER TO postgres;

--
-- Name: legal_regimes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.legal_regimes_id_seq OWNED BY public.legal_regimes.id;


--
-- Name: legal_states; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.legal_states (
    id integer NOT NULL,
    regime_id integer,
    name text NOT NULL,
    state_type character varying(50),
    description text
);


ALTER TABLE public.legal_states OWNER TO postgres;

--
-- Name: legal_states_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.legal_states_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.legal_states_id_seq OWNER TO postgres;

--
-- Name: legal_states_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.legal_states_id_seq OWNED BY public.legal_states.id;


--
-- Name: law_amendments id; Type: DEFAULT; Schema: public; Owner: flaskapp
--

ALTER TABLE ONLY public.law_amendments ALTER COLUMN id SET DEFAULT nextval('public.law_amendments_id_seq'::regclass);


--
-- Name: law_editions id; Type: DEFAULT; Schema: public; Owner: flaskapp
--

ALTER TABLE ONLY public.law_editions ALTER COLUMN id SET DEFAULT nextval('public.law_editions_id_seq'::regclass);


--
-- Name: law_embeddings id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.law_embeddings ALTER COLUMN id SET DEFAULT nextval('public.law_embeddings_id_seq'::regclass);


--
-- Name: law_revisions id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.law_revisions ALTER COLUMN id SET DEFAULT nextval('public.law_revisions_id_seq'::regclass);


--
-- Name: legal_regimes id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.legal_regimes ALTER COLUMN id SET DEFAULT nextval('public.legal_regimes_id_seq'::regclass);


--
-- Name: legal_states id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.legal_states ALTER COLUMN id SET DEFAULT nextval('public.legal_states_id_seq'::regclass);


--
-- Name: law_amendments law_amendments_pkey; Type: CONSTRAINT; Schema: public; Owner: flaskapp
--

ALTER TABLE ONLY public.law_amendments
    ADD CONSTRAINT law_amendments_pkey PRIMARY KEY (id);


--
-- Name: law_editions law_editions_law_id_edition_id_key; Type: CONSTRAINT; Schema: public; Owner: flaskapp
--

ALTER TABLE ONLY public.law_editions
    ADD CONSTRAINT law_editions_law_id_edition_id_key UNIQUE (law_id, edition_id);


--
-- Name: law_editions law_editions_pkey; Type: CONSTRAINT; Schema: public; Owner: flaskapp
--

ALTER TABLE ONLY public.law_editions
    ADD CONSTRAINT law_editions_pkey PRIMARY KEY (id);


--
-- Name: law_embeddings law_embeddings_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.law_embeddings
    ADD CONSTRAINT law_embeddings_pkey PRIMARY KEY (id);


--
-- Name: law_revisions law_revisions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.law_revisions
    ADD CONSTRAINT law_revisions_pkey PRIMARY KEY (id);


--
-- Name: legal_regimes legal_regimes_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.legal_regimes
    ADD CONSTRAINT legal_regimes_pkey PRIMARY KEY (id);


--
-- Name: legal_states legal_states_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.legal_states
    ADD CONSTRAINT legal_states_pkey PRIMARY KEY (id);


--
-- Name: law_amendments unique_consultant_id; Type: CONSTRAINT; Schema: public; Owner: flaskapp
--

ALTER TABLE ONLY public.law_amendments
    ADD CONSTRAINT unique_consultant_id UNIQUE (consultant_id);


--
-- Name: idx_amendments_consultant_id; Type: INDEX; Schema: public; Owner: flaskapp
--

CREATE INDEX idx_amendments_consultant_id ON public.law_amendments USING btree (consultant_id);


--
-- Name: idx_amendments_fz_number; Type: INDEX; Schema: public; Owner: flaskapp
--

CREATE INDEX idx_amendments_fz_number ON public.law_amendments USING btree (fz_number);


--
-- Name: idx_amendments_law_id; Type: INDEX; Schema: public; Owner: flaskapp
--

CREATE INDEX idx_amendments_law_id ON public.law_amendments USING btree (law_id);


--
-- Name: idx_law_editions_law_id; Type: INDEX; Schema: public; Owner: flaskapp
--

CREATE INDEX idx_law_editions_law_id ON public.law_editions USING btree (law_id);


--
-- Name: idx_law_editions_valid_from; Type: INDEX; Schema: public; Owner: flaskapp
--

CREATE INDEX idx_law_editions_valid_from ON public.law_editions USING btree (valid_from);


--
-- Name: idx_law_number; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_law_number ON public.law_embeddings USING btree (law_number);


--
-- Name: idx_law_revisions_current; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_law_revisions_current ON public.law_revisions USING btree (is_current) WHERE (is_current = true);


--
-- Name: idx_law_revisions_date; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_law_revisions_date ON public.law_revisions USING btree (revision_date DESC);


--
-- Name: idx_law_revisions_embedding; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_law_revisions_embedding ON public.law_revisions USING ivfflat (embedding public.vector_cosine_ops) WITH (lists='100');


--
-- Name: idx_law_revisions_law_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_law_revisions_law_id ON public.law_revisions USING btree (law_id);


--
-- Name: law_embeddings_embedding_idx; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX law_embeddings_embedding_idx ON public.law_embeddings USING ivfflat (embedding public.vector_cosine_ops) WITH (lists='100');


--
-- Name: law_amendments fk_law; Type: FK CONSTRAINT; Schema: public; Owner: flaskapp
--

ALTER TABLE ONLY public.law_amendments
    ADD CONSTRAINT fk_law FOREIGN KEY (law_id) REFERENCES public.law_embeddings(id) ON DELETE CASCADE;


--
-- Name: law_revisions fk_law; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.law_revisions
    ADD CONSTRAINT fk_law FOREIGN KEY (law_id) REFERENCES public.law_embeddings(id) ON DELETE CASCADE;


--
-- Name: legal_regimes legal_regimes_parent_regime_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.legal_regimes
    ADD CONSTRAINT legal_regimes_parent_regime_id_fkey FOREIGN KEY (parent_regime_id) REFERENCES public.legal_regimes(id);


--
-- Name: legal_states legal_states_regime_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.legal_states
    ADD CONSTRAINT legal_states_regime_id_fkey FOREIGN KEY (regime_id) REFERENCES public.legal_regimes(id);


--
-- Name: SCHEMA public; Type: ACL; Schema: -; Owner: pg_database_owner
--

GRANT ALL ON SCHEMA public TO flaskapp;


--
-- Name: TABLE law_embeddings; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.law_embeddings TO starec_user;
GRANT ALL ON TABLE public.law_embeddings TO flaskapp;


--
-- Name: SEQUENCE law_embeddings_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.law_embeddings_id_seq TO starec_user;
GRANT ALL ON SEQUENCE public.law_embeddings_id_seq TO flaskapp;


--
-- Name: TABLE law_revisions; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.law_revisions TO flaskapp;


--
-- Name: SEQUENCE law_revisions_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.law_revisions_id_seq TO flaskapp;


--
-- Name: TABLE legal_regimes; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.legal_regimes TO flaskapp;


--
-- Name: SEQUENCE legal_regimes_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.legal_regimes_id_seq TO flaskapp;


--
-- Name: TABLE legal_states; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.legal_states TO flaskapp;


--
-- Name: SEQUENCE legal_states_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.legal_states_id_seq TO flaskapp;


--
-- PostgreSQL database dump complete
--

\unrestrict lfpoIBtgK3B6FBTpgG1RuniNJGsKD1Sb6AfsDiO5juc0RjBhsBKzh7AD88mft6G

