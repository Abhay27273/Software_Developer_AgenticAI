-- filename: schema.sql
-- Description: Complete PostgreSQL schema for the Fitness Tracking Application.
-- This script is idempotent and can be run multiple times safely.

-- Best practice: Wrap the entire schema creation in a transaction
BEGIN;

-- =============================================================================
-- EXTENSIONS
-- =============================================================================
-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";


-- =============================================================================
-- UTILITY FUNCTIONS & TRIGGERS
-- =============================================================================
-- Function to automatically update the 'updated_at' timestamp
CREATE OR REPLACE FUNCTION trigger_set_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;


-- =============================================================================
-- ENUMERATED TYPES (ENUMS)
-- =============================================================================
-- Using ENUM types for data integrity and performance.

DO $$ BEGIN
    CREATE TYPE user_role_enum AS ENUM ('user', 'admin', 'trainer');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE body_part_enum AS ENUM (
        'chest', 'back', 'shoulders', 'biceps', 'triceps',
        'legs', 'abs', 'cardio', 'full_body', 'other'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE exercise_category_enum AS ENUM (
        'strength', 'cardio', 'stretching', 'plyometrics', 'olympic'
    );
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;


-- =============================================================================
-- TABLES
-- =============================================================================

-- Table: users
-- Stores user account information and credentials.
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(100),
    is_active BOOLEAN NOT NULL DEFAULT true,
    role user_role_enum NOT NULL DEFAULT 'user',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Add indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

-- Add trigger for updated_at timestamp
DROP TRIGGER IF EXISTS set_timestamp ON users;
CREATE TRIGGER set_timestamp
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE PROCEDURE trigger_set_timestamp();


-- Table: exercises
-- A catalog of all exercises available in the system.
CREATE TABLE IF NOT EXISTS exercises (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    body_part body_part_enum,
    category exercise_category_enum,
    video_url TEXT,
    -- created_by is nullable for system-defined exercises
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Add indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_exercises_name ON exercises(name);
CREATE INDEX IF NOT EXISTS idx_exercises_body_part ON exercises(body_part);
CREATE INDEX IF NOT EXISTS idx_exercises_category ON exercises(category);

-- Add trigger for updated_at timestamp
DROP TRIGGER IF EXISTS set_timestamp ON exercises;
CREATE TRIGGER set_timestamp
BEFORE UPDATE ON exercises
FOR EACH ROW
EXECUTE PROCEDURE trigger_set_timestamp();


-- Table: workouts
-- Represents a workout template or routine created by a user.
CREATE TABLE IF NOT EXISTS workouts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- A user cannot have two workouts with the same name
    UNIQUE(user_id, name)
);

-- Add index for user's workouts
CREATE INDEX IF NOT EXISTS idx_workouts_user_id ON workouts(user_id);

-- Add trigger for updated_at timestamp
DROP TRIGGER IF EXISTS set_timestamp ON workouts;
CREATE TRIGGER set_timestamp
BEFORE UPDATE ON workouts
FOR EACH ROW
EXECUTE PROCEDURE trigger_set_timestamp();


-- Table: workout_exercises (Join Table)
-- Defines the exercises within a workout template, including sets, reps, and order.
CREATE TABLE IF NOT EXISTS workout_exercises (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workout_id UUID NOT NULL REFERENCES workouts(id) ON DELETE CASCADE,
    exercise_id UUID NOT NULL REFERENCES exercises(id) ON DELETE CASCADE,
    order_index INT NOT NULL, -- To maintain the order of exercises
    sets INT CHECK (sets > 0),
    reps INT CHECK (reps > 0),
    rest_period_seconds INT CHECK (rest_period_seconds >= 0),
    -- An exercise should appear only once at a specific order in a workout
    UNIQUE(workout_id, order_index)
);

-- Add indexes for efficient joins
CREATE INDEX IF NOT EXISTS idx_workout_exercises_workout_id ON workout_exercises(workout_id);
CREATE INDEX IF NOT EXISTS idx_workout_exercises_exercise_id ON workout_exercises(exercise_id);


-- Table: workout_logs
-- Records an instance of a completed workout session by a user.
CREATE TABLE IF NOT EXISTS workout_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    -- workout_id is nullable to allow for ad-hoc, non-template workouts
    workout_id UUID REFERENCES workouts(id) ON DELETE SET NULL,
    start_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    end_time TIMESTAMPTZ,
    notes TEXT,
    -- Ensure end_time is after start_time
    CONSTRAINT check_end_time CHECK (end_time IS NULL OR end_time >= start_time)
);

-- Add indexes for querying logs
CREATE INDEX IF NOT EXISTS idx_workout_logs_user_id ON workout_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_workout_logs_start_time ON workout_logs(start_time DESC);


-- Table: exercise_logs
-- Records details of a specific exercise performed within a workout_log.
CREATE TABLE IF NOT EXISTS exercise_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workout_log_id UUID NOT NULL REFERENCES workout_logs(id) ON DELETE CASCADE,
    exercise_id UUID NOT NULL REFERENCES exercises(id) ON DELETE CASCADE,
    notes TEXT
);

-- Add indexes for efficient joins
CREATE INDEX IF NOT EXISTS idx_exercise_logs_workout_log_id ON exercise_logs(workout_log_id);
CREATE INDEX IF NOT EXISTS idx_exercise_logs_exercise_id ON exercise_logs(exercise_id);


-- Table: set_logs
-- The most granular log, recording each set performed for an exercise.
CREATE TABLE IF NOT EXISTS set_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    exercise_log_id UUID NOT NULL REFERENCES exercise_logs(id) ON DELETE CASCADE,
    set_number INT NOT NULL CHECK (set_number > 0),
    reps_completed INT CHECK (reps_completed >= 0),
    -- Precision 7, scale 2. E.g., 99999.99
    weight NUMERIC(7, 2) CHECK (weight >= 0),
    duration_seconds INT CHECK (duration_seconds >= 0),
    distance_meters INT CHECK (distance_meters >= 0),
    -- A set number should be unique for a given exercise log
    UNIQUE(exercise_log_id, set_number)
);

-- Add index for efficient joins
CREATE INDEX IF NOT EXISTS idx_set_logs_exercise_log_id ON set_logs(exercise_log_id);

COMMIT;