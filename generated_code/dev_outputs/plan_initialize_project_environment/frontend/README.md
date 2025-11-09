# Frontend Service (React with Vite)

This directory contains the frontend service for the project, built with React and Vite.

## Features

*   **React 18**: Modern JavaScript library for building user interfaces.
*   **Vite**: Fast development server and build tool.
*   **Tailwind CSS**: Utility-first CSS framework for rapid UI development.
*   **ESLint**: Code linting for quality and consistency.
*   **Dockerization**: Containerized for easy deployment.

## Development

### Local Setup

1.  **Navigate**: `cd frontend/`
2.  **Install Dependencies**: `npm install` (or `yarn install`)
3.  **Environment Variables**: Create a `.env` file based on `.env.example`.
4.  **Run Development Server**: `npm run dev` (or `yarn dev`)
    *   The frontend will be available at `http://localhost:5173`.

### Building for Production

1.  **Navigate**: `cd frontend/`
2.  **Build**: `npm run build` (or `yarn build`)
    *   This will create a `dist/` directory with optimized static assets.

## Deployment

Refer to the root `docker-compose.yml` for containerized deployment.