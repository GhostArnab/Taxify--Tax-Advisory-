import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.getenv('DB_URL')

userfinancials_table = '''
CREATE TABLE IF NOT EXISTS UserFinancials (
    session_id UUID PRIMARY KEY,
    gross_salary NUMERIC(15, 2),
    basic_salary NUMERIC(15, 2),
    hra_received NUMERIC(15, 2),
    rent_paid NUMERIC(15, 2),
    deduction_80c NUMERIC(15, 2),
    deduction_80d NUMERIC(15, 2),
    standard_deduction NUMERIC(15, 2),
    professional_tax NUMERIC(15, 2),
    tds NUMERIC(15, 2),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
'''

taxcomparison_table = '''
CREATE TABLE IF NOT EXISTS TaxComparison (
    session_id UUID PRIMARY KEY REFERENCES UserFinancials(session_id),
    tax_old_regime NUMERIC(15, 2),
    tax_new_regime NUMERIC(15, 2),
    best_regime VARCHAR(10),
    selected_regime VARCHAR(10),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
'''

conversationlog_table = '''
CREATE TABLE IF NOT EXISTS ConversationLog (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES UserFinancials(session_id),
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    timestamp TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_conversationlog_session ON ConversationLog(session_id);
'''

# --- Row Level Security ---
# Enable RLS and deny all access via the public API (anon/authenticated roles).
# The backend connects with the postgres (superuser) role via DB_URL,
# which bypasses RLS, so app functionality is unaffected.
enable_rls = '''
ALTER TABLE public.userfinancials ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.taxcomparison ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.conversationlog ENABLE ROW LEVEL SECURITY;
'''

rls_policies = '''
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE tablename = 'userfinancials' AND policyname = 'Deny anon access on userfinancials'
    ) THEN
        CREATE POLICY "Deny anon access on userfinancials"
            ON public.userfinancials FOR ALL USING (false);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE tablename = 'taxcomparison' AND policyname = 'Deny anon access on taxcomparison'
    ) THEN
        CREATE POLICY "Deny anon access on taxcomparison"
            ON public.taxcomparison FOR ALL USING (false);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE tablename = 'conversationlog' AND policyname = 'Deny anon access on conversationlog'
    ) THEN
        CREATE POLICY "Deny anon access on conversationlog"
            ON public.conversationlog FOR ALL USING (false);
    END IF;
END
$$;
'''

def main():
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute(userfinancials_table)
        cur.execute(taxcomparison_table)
        cur.execute(conversationlog_table)
        cur.execute(enable_rls)
        cur.execute(rls_policies)
        conn.commit()
        cur.close()
        conn.close()
        print('Tables created successfully.')
    except Exception as e:
        print('Error creating tables:', e)

if __name__ == '__main__':
    main() 