-- Migration: Enable pgvector extension and create embedding tables
-- Part of Sprint 1: Foundation & Admin Backend
-- Required for AI-powered candidate matching (Sprint 4)

-- Enable pgvector extension (requires superuser or enabled in Supabase dashboard)
-- Note: In Supabase, go to Database > Extensions and enable 'vector'
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================================
-- CANDIDATE EMBEDDINGS
-- Store vector embeddings for candidate resumes and profiles
-- ============================================================================

CREATE TABLE IF NOT EXISTS candidate_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    candidate_id UUID NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    resume_id UUID REFERENCES resumes(id) ON DELETE SET NULL,

    -- Embedding vector (1536 dimensions for text-embedding-ada-002)
    embedding vector(1536) NOT NULL,

    -- Type of embedding: 'resume_full', 'skills', 'experience', 'summary'
    embedding_type VARCHAR(50) NOT NULL DEFAULT 'resume_full',

    -- Source text that was embedded (for debugging/auditing)
    source_text_hash VARCHAR(64),  -- SHA256 hash to detect changes

    -- Model used for embedding
    model_name VARCHAR(100) DEFAULT 'text-embedding-ada-002',
    model_version VARCHAR(50),

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT unique_candidate_embedding_type UNIQUE (candidate_id, embedding_type)
);

-- Index for fast similarity search
CREATE INDEX IF NOT EXISTS idx_candidate_embeddings_vector
    ON candidate_embeddings USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Index for filtering by type
CREATE INDEX IF NOT EXISTS idx_candidate_embeddings_type
    ON candidate_embeddings(tenant_id, embedding_type);

-- Index for candidate lookup
CREATE INDEX IF NOT EXISTS idx_candidate_embeddings_candidate
    ON candidate_embeddings(candidate_id);

-- ============================================================================
-- JOB EMBEDDINGS
-- Store vector embeddings for job requisition descriptions and requirements
-- ============================================================================

CREATE TABLE IF NOT EXISTS job_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    requisition_id UUID NOT NULL REFERENCES job_requisitions(id) ON DELETE CASCADE,

    -- Embedding vector (1536 dimensions for text-embedding-ada-002)
    embedding vector(1536) NOT NULL,

    -- Type of embedding: 'description', 'requirements', 'full'
    embedding_type VARCHAR(50) NOT NULL DEFAULT 'full',

    -- Source text hash
    source_text_hash VARCHAR(64),

    -- Model info
    model_name VARCHAR(100) DEFAULT 'text-embedding-ada-002',
    model_version VARCHAR(50),

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT unique_job_embedding_type UNIQUE (requisition_id, embedding_type)
);

-- Index for fast similarity search
CREATE INDEX IF NOT EXISTS idx_job_embeddings_vector
    ON job_embeddings USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Index for filtering
CREATE INDEX IF NOT EXISTS idx_job_embeddings_type
    ON job_embeddings(tenant_id, embedding_type);

-- Index for requisition lookup
CREATE INDEX IF NOT EXISTS idx_job_embeddings_requisition
    ON job_embeddings(requisition_id);

-- ============================================================================
-- CANDIDATE MATCHES
-- Pre-computed match scores between candidates and job requisitions
-- ============================================================================

CREATE TABLE IF NOT EXISTS candidate_matches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    candidate_id UUID NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    requisition_id UUID NOT NULL REFERENCES job_requisitions(id) ON DELETE CASCADE,

    -- Overall match score (0.0000 to 1.0000)
    match_score DECIMAL(5,4) NOT NULL CHECK (match_score >= 0 AND match_score <= 1),

    -- Detailed breakdown of match components
    match_breakdown JSONB DEFAULT '{}'::jsonb,
    -- Example: {
    --   "embedding_similarity": 0.85,
    --   "skills_match": 0.72,
    --   "experience_match": 0.68,
    --   "education_match": 0.90,
    --   "location_match": 1.00
    -- }

    -- Whether this is a recommended match (above threshold)
    is_recommended BOOLEAN DEFAULT FALSE,

    -- Rank among all matches for this job
    match_rank INT,

    -- When the match was calculated
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Algorithm/model version used
    algorithm_version VARCHAR(50) DEFAULT 'v1',

    -- Constraints
    CONSTRAINT unique_candidate_job_match UNIQUE (candidate_id, requisition_id)
);

-- Index for finding best candidates for a job
CREATE INDEX IF NOT EXISTS idx_candidate_matches_job_score
    ON candidate_matches(requisition_id, match_score DESC);

-- Index for finding best jobs for a candidate
CREATE INDEX IF NOT EXISTS idx_candidate_matches_candidate_score
    ON candidate_matches(candidate_id, match_score DESC);

-- Index for recommended matches only
CREATE INDEX IF NOT EXISTS idx_candidate_matches_recommended
    ON candidate_matches(requisition_id, is_recommended)
    WHERE is_recommended = TRUE;

-- Index for tenant filtering
CREATE INDEX IF NOT EXISTS idx_candidate_matches_tenant
    ON candidate_matches(tenant_id);

-- ============================================================================
-- EMBEDDING GENERATION QUEUE
-- Track pending and completed embedding generation tasks
-- ============================================================================

CREATE TABLE IF NOT EXISTS embedding_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,

    -- What to embed
    entity_type VARCHAR(50) NOT NULL,  -- 'candidate', 'job'
    entity_id UUID NOT NULL,

    -- Task status: 'pending', 'processing', 'completed', 'failed'
    status VARCHAR(20) NOT NULL DEFAULT 'pending',

    -- Priority (lower = higher priority)
    priority INT DEFAULT 100,

    -- Processing details
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error_message TEXT,
    retry_count INT DEFAULT 0,
    max_retries INT DEFAULT 3,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT unique_embedding_task UNIQUE (entity_type, entity_id)
);

-- Index for finding pending tasks
CREATE INDEX IF NOT EXISTS idx_embedding_tasks_pending
    ON embedding_tasks(status, priority, created_at)
    WHERE status = 'pending';

-- Index for cleanup
CREATE INDEX IF NOT EXISTS idx_embedding_tasks_completed
    ON embedding_tasks(completed_at)
    WHERE status = 'completed';

-- ============================================================================
-- ROW LEVEL SECURITY (RLS)
-- ============================================================================

-- Enable RLS on all embedding tables
ALTER TABLE candidate_embeddings ENABLE ROW LEVEL SECURITY;
ALTER TABLE job_embeddings ENABLE ROW LEVEL SECURITY;
ALTER TABLE candidate_matches ENABLE ROW LEVEL SECURITY;
ALTER TABLE embedding_tasks ENABLE ROW LEVEL SECURITY;

-- RLS Policies for candidate_embeddings
CREATE POLICY "tenant_isolation_candidate_embeddings" ON candidate_embeddings
    FOR ALL USING (
        tenant_id = (current_setting('app.current_tenant_id', true))::uuid
    );

-- RLS Policies for job_embeddings
CREATE POLICY "tenant_isolation_job_embeddings" ON job_embeddings
    FOR ALL USING (
        tenant_id = (current_setting('app.current_tenant_id', true))::uuid
    );

-- RLS Policies for candidate_matches
CREATE POLICY "tenant_isolation_candidate_matches" ON candidate_matches
    FOR ALL USING (
        tenant_id = (current_setting('app.current_tenant_id', true))::uuid
    );

-- RLS Policies for embedding_tasks
CREATE POLICY "tenant_isolation_embedding_tasks" ON embedding_tasks
    FOR ALL USING (
        tenant_id = (current_setting('app.current_tenant_id', true))::uuid
    );

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Function to find similar candidates for a job
CREATE OR REPLACE FUNCTION find_similar_candidates(
    p_requisition_id UUID,
    p_limit INT DEFAULT 20,
    p_min_score FLOAT DEFAULT 0.5
)
RETURNS TABLE (
    candidate_id UUID,
    similarity_score FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ce.candidate_id,
        1 - (ce.embedding <=> je.embedding) as similarity_score
    FROM candidate_embeddings ce
    CROSS JOIN job_embeddings je
    WHERE je.requisition_id = p_requisition_id
      AND je.embedding_type = 'full'
      AND ce.embedding_type = 'resume_full'
      AND ce.tenant_id = je.tenant_id
      AND 1 - (ce.embedding <=> je.embedding) >= p_min_score
    ORDER BY ce.embedding <=> je.embedding
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Function to find similar jobs for a candidate
CREATE OR REPLACE FUNCTION find_similar_jobs(
    p_candidate_id UUID,
    p_limit INT DEFAULT 10,
    p_min_score FLOAT DEFAULT 0.5
)
RETURNS TABLE (
    requisition_id UUID,
    similarity_score FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        je.requisition_id,
        1 - (je.embedding <=> ce.embedding) as similarity_score
    FROM job_embeddings je
    CROSS JOIN candidate_embeddings ce
    WHERE ce.candidate_id = p_candidate_id
      AND ce.embedding_type = 'resume_full'
      AND je.embedding_type = 'full'
      AND je.tenant_id = ce.tenant_id
    ORDER BY je.embedding <=> ce.embedding
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- Function to update embedding updated_at timestamp
CREATE OR REPLACE FUNCTION update_embedding_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for updated_at
CREATE TRIGGER update_candidate_embeddings_timestamp
    BEFORE UPDATE ON candidate_embeddings
    FOR EACH ROW EXECUTE FUNCTION update_embedding_timestamp();

CREATE TRIGGER update_job_embeddings_timestamp
    BEFORE UPDATE ON job_embeddings
    FOR EACH ROW EXECUTE FUNCTION update_embedding_timestamp();

CREATE TRIGGER update_embedding_tasks_timestamp
    BEFORE UPDATE ON embedding_tasks
    FOR EACH ROW EXECUTE FUNCTION update_embedding_timestamp();

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE candidate_embeddings IS 'Vector embeddings for candidate resumes and profiles, used for AI-powered matching';
COMMENT ON TABLE job_embeddings IS 'Vector embeddings for job requisitions, used for AI-powered candidate matching';
COMMENT ON TABLE candidate_matches IS 'Pre-computed match scores between candidates and jobs for fast retrieval';
COMMENT ON TABLE embedding_tasks IS 'Queue for pending embedding generation tasks';

COMMENT ON FUNCTION find_similar_candidates IS 'Find candidates most similar to a job requisition using vector similarity';
COMMENT ON FUNCTION find_similar_jobs IS 'Find job requisitions most similar to a candidate profile using vector similarity';
