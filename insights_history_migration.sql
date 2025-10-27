-- Migration: Create insights_history table
-- Purpose: Store user's insights analysis history with automatic cleanup

-- Create insights_history table
CREATE TABLE IF NOT EXISTS public.insights_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    ticker VARCHAR(20) NOT NULL,
    asset_type VARCHAR(20) NOT NULL DEFAULT 'stock',
    analysis_type VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_insights_history_user_id ON public.insights_history(user_id);
CREATE INDEX IF NOT EXISTS idx_insights_history_ticker ON public.insights_history(ticker);
CREATE INDEX IF NOT EXISTS idx_insights_history_analysis_type ON public.insights_history(analysis_type);
CREATE INDEX IF NOT EXISTS idx_insights_history_created_at ON public.insights_history(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_insights_history_user_created ON public.insights_history(user_id, created_at DESC);

-- Create composite index for common queries
CREATE INDEX IF NOT EXISTS idx_insights_history_user_ticker_type ON public.insights_history(user_id, ticker, analysis_type, created_at DESC);

-- Enable Row Level Security (RLS)
ALTER TABLE public.insights_history ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Users can only view their own insights history
CREATE POLICY "Users can view their own insights history"
    ON public.insights_history
    FOR SELECT
    USING (auth.uid() = user_id);

-- RLS Policy: Users can insert their own insights history
CREATE POLICY "Users can insert their own insights history"
    ON public.insights_history
    FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- RLS Policy: Users can delete their own insights history
CREATE POLICY "Users can delete their own insights history"
    ON public.insights_history
    FOR DELETE
    USING (auth.uid() = user_id);

-- RLS Policy: Users can update their own insights history
CREATE POLICY "Users can update their own insights history"
    ON public.insights_history
    FOR UPDATE
    USING (auth.uid() = user_id);

-- Function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_insights_history_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to update updated_at on row update
CREATE TRIGGER trigger_insights_history_updated_at
    BEFORE UPDATE ON public.insights_history
    FOR EACH ROW
    EXECUTE FUNCTION update_insights_history_updated_at();

-- Function to cleanup old insights (keep only 10 most recent per user per analysis_type)
CREATE OR REPLACE FUNCTION cleanup_old_insights_history()
RETURNS TRIGGER AS $$
BEGIN
    -- Delete old records for this user and analysis_type, keeping only 10 most recent
    DELETE FROM public.insights_history
    WHERE id IN (
        SELECT id
        FROM public.insights_history
        WHERE user_id = NEW.user_id 
          AND analysis_type = NEW.analysis_type
        ORDER BY created_at DESC
        OFFSET 10
    );
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to automatically cleanup after insert
CREATE TRIGGER trigger_cleanup_old_insights
    AFTER INSERT ON public.insights_history
    FOR EACH ROW
    EXECUTE FUNCTION cleanup_old_insights_history();

-- Grant permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON public.insights_history TO authenticated;
GRANT USAGE ON SCHEMA public TO authenticated;

-- Comment on table and columns
COMMENT ON TABLE public.insights_history IS 'Stores user insights analysis history with automatic cleanup (max 10 per analysis type)';
COMMENT ON COLUMN public.insights_history.id IS 'Unique identifier for the insight record';
COMMENT ON COLUMN public.insights_history.user_id IS 'Reference to the user who requested the analysis';
COMMENT ON COLUMN public.insights_history.ticker IS 'Stock ticker symbol (e.g., VCB, BTC)';
COMMENT ON COLUMN public.insights_history.asset_type IS 'Type of asset: stock, crypto';
COMMENT ON COLUMN public.insights_history.analysis_type IS 'Type of analysis: technical_analysis, news_analysis, proprietary_trading_analysis, etc.';
COMMENT ON COLUMN public.insights_history.content IS 'The analysis content/result';
COMMENT ON COLUMN public.insights_history.metadata IS 'Additional metadata (dates, parameters, etc.)';
COMMENT ON COLUMN public.insights_history.created_at IS 'Timestamp when the analysis was created';
COMMENT ON COLUMN public.insights_history.updated_at IS 'Timestamp when the record was last updated';
