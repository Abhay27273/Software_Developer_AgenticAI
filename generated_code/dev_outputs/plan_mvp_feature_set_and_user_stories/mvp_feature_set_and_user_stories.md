# Fitness Tracker: MVP Feature Set & User Stories

## 1. Finalized MVP Feature Set

This document outlines the core features ("Epics") that constitute the Minimum Viable Product (MVP) for the Fitness Tracker application. The development team and stakeholders have signed off on this list.

*   **Epic 1: Authentication & User Management**
    *   Core functionality for user registration, login, logout, and basic account security.
*   **Epic 2: Workout Logging**
    *   The primary feature allowing users to create, manage, and record their workout sessions and the exercises within them.
*   **Epic 3: Progress Tracking**
    *   Visual and data-driven feedback for users to track their performance and progress over time.
*   **Epic 4: User Profile**
    *   A dedicated space for users to view and manage their personal information.

---

## 2. User Stories & Acceptance Criteria

Below are the detailed user stories for each feature set. These stories will guide the development and testing for the MVP.

### Epic 1: Authentication & User Management

**Story 1.1: New User Registration**
*   **As a** new visitor,
*   **I want to** create a new account using my email and a password,
*   **So that** I can start logging my workouts and tracking my progress.

*   **Acceptance Criteria:**
    *   **Given** a user is on the registration page,
    *   **When** they enter a valid, unique email address and a password that meets the complexity requirements (e.g., 8+ characters, 1 uppercase, 1 number),
    *   **Then** their account is created successfully, their password is securely hashed and stored, and they are automatically logged in and redirected to the main dashboard.
    *   **Given** a user attempts to register with an email that already exists,
    *   **When** they submit the form,
    *   **Then** a clear error message is displayed indicating the email is already in use.
    *   **Given** a user enters an invalid email format or a weak password,
    *   **When** they submit the form,
    *   **Then** a validation error message is displayed, and the account is not created.

**Story 1.2: User Login**
*   **As a** registered user,
*   **I want to** log in with my email and password,
*   **So that** I can access my personal dashboard and workout data.

*   **Acceptance Criteria:**
    *   **Given** a registered user is on the login page,
    *   **When** they enter their correct email and password,
    *   **Then** they are successfully authenticated, a secure session token (JWT) is issued, and they are redirected to their dashboard.
    *   **Given** a user enters incorrect credentials,
    *   **When** they attempt to log in,
    *   **Then** an "Invalid email or password" error message is displayed, and they remain on the login page.

**Story 1.3: User Logout**
*   **As a** logged-in user,
*   **I want to** log out of the application,
*   **So that** I can securely end my session.

*   **Acceptance Criteria:**
    *   **Given** a user is logged in,
    *   **When** they click the "Logout" button,
    *   **Then** their session token is invalidated on the client-side (and server-side if using a blacklist), and they are redirected to the public home or login page.

---

### Epic 2: Workout Logging

**Story 2.1: Create a New Workout Log**
*   **As a** logged-in user,
*   **I want to** start a new, empty workout session for the current day,
*   **So that** I can begin adding exercises to it.

*   **Acceptance Criteria:**
    *   **Given** a user is on their dashboard or workout page,
    *   **When** they click "Start New Workout",
    *   **Then** a new workout record is created with the current date, and they are taken to a view where they can add exercises to this new workout.

**Story 2.2: Add an Exercise to a Workout**
*   **As a** logged-in user,
*   **I want to** add an exercise with its sets, reps, and weight to my current workout log,
*   **So that** I can accurately record my training activity.

*   **Acceptance Criteria:**
    *   **Given** a user is actively logging a workout,
    *   **When** they add an exercise,
    *   **Then** they can input the exercise name, the number of sets, and the reps and weight for each set.
    *   **Given** a user is adding an exercise,
    *   **When** they start typing the exercise name,
    *   **Then** an autocomplete suggests exercises from a predefined list (e.g., "Bench Press", "Squat").
    *   **Given** the exercise is not in the predefined list,
    *   **When** the user types a new exercise name and adds sets,
    *   **Then** the new exercise is saved for future use.

**Story 2.3: View Past Workouts**
*   **As a** logged-in user,
*   **I want to** view a chronological list of my past workouts,
*   **So that** I can review my training history.

*   **Acceptance Criteria:**
    *   **Given** a user navigates to their workout history page,
    *   **When** the page loads,
    *   **Then** a list of all their past workout sessions is displayed, sorted by date in descending order.
    *   **Given** the user is viewing their workout history,
    *   **When** they click on a specific workout session,
    *   **Then** they are taken to a detailed view showing all exercises and sets performed during that session.

---

### Epic 3: Progress Tracking

**Story 3.1: View Progress for a Specific Exercise**
*   **As a** logged-in user,
*   **I want to** see my performance history for a single exercise,
*   **So that** I can track my strength and volume progression over time.

*   **Acceptance Criteria:**
    *   **Given** a user is on the progress tracking page,
    *   **When** they select an exercise (e.g., "Deadlift"),
    *   **Then** a chart is displayed showing their one-rep max estimate or total volume for that exercise over time.
    *   **Given** the user is viewing the progress chart,
    *   **When** the data is displayed,
    *   **Then** they can also see a table listing every set they have ever logged for that exercise, sorted by date.

**Story 3.2: Dashboard Overview**
*   **As a** logged-in user,
*   **I want to** see a high-level summary of my recent activity on my dashboard,
*   **So that** I can get a quick snapshot of my consistency and achievements.

*   **Acceptance Criteria:**
    *   **Given** a user logs in and lands on the dashboard,
    *   **When** the page loads,
    *   **Then** it displays key metrics such as:
        *   Total workouts this month.
        *   Date of the last workout.
        *   A list of recent Personal Records (PRs) for major lifts.

---

### Epic 4: User Profile

**Story 4.1: View and Edit Profile Information**
*   **As a** logged-in user,
*   **I want to** view and edit my personal information, such as my name and bodyweight,
*   **So that** I can keep my profile accurate.

*   **Acceptance Criteria:**
    *   **Given** a user navigates to their profile page,
    *   **When** the page loads,
    *   **Then** it displays their username, email (read-only), and other saved details like bodyweight.
    *   **Given** a user is on their profile page,
    *   **When** they update their username or bodyweight and click "Save",
    *   **Then** the new information is persisted to the database, and a success message is shown.