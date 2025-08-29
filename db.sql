-- ENABLE EXTENSIONS
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- USERS
CREATE TABLE users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email text UNIQUE NOT NULL,
    password_hash text NOT NULL,
    full_name text,
    phone text,
    avatar_url text,
    is_active boolean DEFAULT true,
    email_verified boolean DEFAULT false,
    last_login_at timestamptz,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

-- USER PROFILES
CREATE TABLE user_profiles (
    user_id uuid PRIMARY KEY REFERENCES users(id),
    bio text,
    profile_picture_url text,
    followers_count int DEFAULT 0,
    following_count int DEFAULT 0,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;

-- FOLLOWS
CREATE TABLE follows (
    follower_id uuid REFERENCES users(id) ON DELETE CASCADE,
    following_id uuid REFERENCES users(id) ON DELETE CASCADE,
    followed_at timestamptz DEFAULT now(),
    PRIMARY KEY (follower_id, following_id)
);
ALTER TABLE follows ENABLE ROW LEVEL SECURITY;

-- POSTS
CREATE TABLE posts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid REFERENCES users(id) ON DELETE CASCADE,
    title text NOT NULL,
    content jsonb DEFAULT '[]',
    tags jsonb DEFAULT '[]',
    likes_count int DEFAULT 0,
    comments_count int DEFAULT 0,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);
ALTER TABLE posts ENABLE ROW LEVEL SECURITY;

-- COMMENTS
CREATE TABLE comments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id uuid REFERENCES posts(id) ON DELETE CASCADE,
    user_id uuid REFERENCES users(id) ON DELETE CASCADE,
    content text NOT NULL,
    created_at timestamptz DEFAULT now()
);
ALTER TABLE comments ENABLE ROW LEVEL SECURITY;

-- ROLES
CREATE TABLE roles (
    id serial PRIMARY KEY,
    name text UNIQUE NOT NULL,
    description text,
    permissions jsonb DEFAULT '{}',
    created_at timestamptz DEFAULT now()
);
ALTER TABLE roles ENABLE ROW LEVEL SECURITY;

-- USER ROLES
CREATE TABLE user_roles (
    user_id uuid REFERENCES users(id) ON DELETE CASCADE,
    role_id int REFERENCES roles(id) ON DELETE CASCADE,
    assigned_at timestamptz DEFAULT now(),
    assigned_by uuid REFERENCES users(id),
    PRIMARY KEY (user_id, role_id)
);
ALTER TABLE user_roles ENABLE ROW LEVEL SECURITY;

-- AUTH PROVIDERS
CREATE TABLE auth_providers (
    id serial PRIMARY KEY,
    user_id uuid REFERENCES users(id) ON DELETE CASCADE,
    provider text NOT NULL,
    provider_user_id text,
    provider_data jsonb,
    created_at timestamptz DEFAULT now()
);
ALTER TABLE auth_providers ENABLE ROW LEVEL SECURITY;

-- WALLETS
CREATE TABLE wallets (
    user_id uuid PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    balance numeric(18,2) DEFAULT 0 CHECK (balance >= 0),
    locked_balance numeric(18,2) DEFAULT 0 CHECK (locked_balance >= 0),
    total_earned numeric(18,2) DEFAULT 0,
    total_spent numeric(18,2) DEFAULT 0,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);
ALTER TABLE wallets ENABLE ROW LEVEL SECURITY;

-- WALLET TRANSACTIONS
CREATE TABLE wallet_transactions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid REFERENCES users(id) ON DELETE CASCADE,
    transaction_type text NOT NULL,
    amount numeric(18,2) NOT NULL,
    balance_before numeric(18,2) NOT NULL,
    balance_after numeric(18,2) NOT NULL,
    description text,
    related_type text,
    related_id text,
    metadata jsonb,
    status text DEFAULT 'completed',
    created_at timestamptz DEFAULT now(),
    processed_at timestamptz
);
ALTER TABLE wallet_transactions ENABLE ROW LEVEL SECURITY;

-- PACKAGES
CREATE TABLE packages (
    id serial PRIMARY KEY,
    name text NOT NULL,
    description text,
    price numeric(18,2) NOT NULL CHECK (price > 0),
    coin_amount int NOT NULL CHECK (coin_amount > 0),
    duration_days int NOT NULL CHECK (duration_days > 0),
    features jsonb DEFAULT '[]',
    is_active boolean DEFAULT true,
    sort_order int DEFAULT 0,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);
ALTER TABLE packages ENABLE ROW LEVEL SECURITY;

-- USER PACKAGES
CREATE TABLE user_packages (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid REFERENCES users(id) ON DELETE CASCADE,
    package_id int REFERENCES packages(id),
    start_date date NOT NULL,
    end_date date NOT NULL,
    status text DEFAULT 'active',
    auto_renewal boolean DEFAULT false,
    purchased_price numeric(18,2),
    coins_received int,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);
ALTER TABLE user_packages ENABLE ROW LEVEL SECURITY;

-- PAYMENTS
CREATE TABLE payments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid REFERENCES users(id) ON DELETE CASCADE,
    amount numeric(18,2) NOT NULL CHECK (amount > 0),
    currency text DEFAULT 'VND',
    payment_method text NOT NULL,
    status text DEFAULT 'pending',
    external_transaction_id text,
    gateway_response jsonb,
    coins_amount int,
    notes text,
    processed_at timestamptz,
    expires_at timestamptz,
    created_at timestamptz DEFAULT now()
);
ALTER TABLE payments ENABLE ROW LEVEL SECURITY;

-- INVITES
CREATE TABLE invites (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    inviter_id uuid REFERENCES users(id) ON DELETE CASCADE,
    invitee_email text NOT NULL,
    invitee_id uuid REFERENCES users(id) ON DELETE SET NULL,
    invite_code text UNIQUE NOT NULL,
    status text DEFAULT 'pending',
    bonus_coin_inviter int DEFAULT 0,
    bonus_coin_invitee int DEFAULT 0,
    bonus_awarded boolean DEFAULT false,
    invited_at timestamptz DEFAULT now(),
    accepted_at timestamptz,
    expires_at timestamptz DEFAULT (now() + interval '7 days')
);
ALTER TABLE invites ENABLE ROW LEVEL SECURITY;

-- EVENTS
CREATE TABLE events (
    id serial PRIMARY KEY,
    name text NOT NULL,
    description text,
    event_type text DEFAULT 'promotion',
    start_date timestamptz NOT NULL,
    end_date timestamptz NOT NULL,
    coin_reward int DEFAULT 0,
    max_participants int,
    current_participants int DEFAULT 0,
    rules jsonb DEFAULT '{}',
    is_active boolean DEFAULT true,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);
ALTER TABLE events ENABLE ROW LEVEL SECURITY;

-- EVENT PARTICIPANTS
CREATE TABLE event_participants (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id int REFERENCES events(id) ON DELETE CASCADE,
    user_id uuid REFERENCES users(id) ON DELETE CASCADE,
    participation_data jsonb DEFAULT '{}',
    reward_coins int DEFAULT 0,
    reward_received boolean DEFAULT false,
    joined_at timestamptz DEFAULT now(),
    completed_at timestamptz,
    UNIQUE(event_id, user_id)
);
ALTER TABLE event_participants ENABLE ROW LEVEL SECURITY;

-- SERVICE USAGE
CREATE TABLE service_usage (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid REFERENCES users(id) ON DELETE CASCADE,
    service_type text NOT NULL,
    coins_spent int DEFAULT 0,
    request_data jsonb,
    response_data jsonb,
    execution_time_ms int,
    ip_address inet,
    created_at timestamptz DEFAULT now()
);
ALTER TABLE service_usage ENABLE ROW LEVEL SECURITY;

-- NOTIFICATIONS
CREATE TABLE notifications (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid REFERENCES users(id) ON DELETE CASCADE,
    title text NOT NULL,
    message text NOT NULL,
    notification_type text DEFAULT 'info',
    is_read boolean DEFAULT false,
    action_url text,
    metadata jsonb,
    created_at timestamptz DEFAULT now(),
    read_at timestamptz
);
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;

-- ADMIN LOGS
CREATE TABLE admin_logs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    admin_id uuid REFERENCES users(id) ON DELETE SET NULL,
    action text NOT NULL,
    target_type text,
    target_id text,
    old_values jsonb,
    new_values jsonb,
    ip_address inet,
    user_agent text,
    created_at timestamptz DEFAULT now()
);
ALTER TABLE admin_logs ENABLE ROW LEVEL SECURITY;

-- SYSTEM SETTINGS
CREATE TABLE system_settings (
    key text PRIMARY KEY,
    value text,
    value_type text DEFAULT 'string',
    description text,
    is_public boolean DEFAULT false,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);
ALTER TABLE system_settings ENABLE ROW LEVEL SECURITY;

-- ERROR LOGS
CREATE TABLE error_logs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid REFERENCES users(id) ON DELETE SET NULL,
    error_type text NOT NULL,
    error_message text NOT NULL,
    stack_trace text,
    request_url text,
    request_method text,
    request_data jsonb,
    ip_address inet,
    user_agent text,
    created_at timestamptz DEFAULT now()
);
ALTER TABLE error_logs ENABLE ROW LEVEL SECURITY;
