# Unity Catalog Swiss Army Knife

A comprehensive tool for managing Databricks Unity Catalog resources, featuring a React frontend and Flask backend.

![Home](docs/images/home.png)

## Overview

The Unity Catalog Swiss Army Knife provides a unified interface for managing various aspects of Databricks Unity Catalog, including:

- Data Products management
- Data Contracts handling
- Business Glossaries
- Master Data Management
- Advanced Catalog operations

## Architecture

### Frontend (React + TypeScript)

The frontend is built with React and Material-UI, providing a modern and responsive user interface.

Key features:
- Tab-based navigation
- Real-time data synchronization
- Interactive data management interfaces
- Responsive dashboard with summary metrics
- Material Design components

### Backend (Python + Flask)

The backend API is built with Flask, providing RESTful endpoints for all data operations.

#### API Endpoints

##### Data Products

# Getting Started with Create React App

This project was bootstrapped with [Create React App](https://github.com/facebook/create-react-app).

## Available Scripts

In the project directory, you can run:

### `npm start`

Runs the app in the development mode.\
Open [http://localhost:3000](http://localhost:3000) to view it in the browser.

The page will reload if you make edits.\
You will also see any lint errors in the console.

### `npm start-api`

Runs the Python based API server in the development mode.

The page will reload if you make edits.\
You will also see any lint errors in the console.

### `npm test`

Launches the test runner in the interactive watch mode.\
See the section about [running tests](https://facebook.github.io/create-react-app/docs/running-tests) for more information.

### `npm run build`

Builds the app for production to the `build` folder.\
It correctly bundles React in production mode and optimizes the build for the best performance.

The build is minified and the filenames include the hashes.\
Your app is ready to be deployed!

See the section about [deployment](https://facebook.github.io/create-react-app/docs/deployment) for more information.

### `npm run eject`

**Note: this is a one-way operation. Once you `eject`, you can't go back!**

If you aren't satisfied with the build tool and configuration choices, you can `eject` at any time. This command will remove the single build dependency from your project.

Instead, it will copy all the configuration files and the transitive dependencies (webpack, Babel, ESLint, etc) right into your project so you have full control over them. All of the commands except `eject` will still work, but they will point to the copied scripts so you can tweak them. At this point you're on your own.

You don't have to ever use `eject`. The curated feature set is suitable for small and middle deployments, and you shouldn't feel obligated to use this feature. However we understand that this tool wouldn't be useful if you couldn't customize it when you are ready for it.

## Learn More

You can learn more in the [Create React App documentation](https://facebook.github.io/create-react-app/docs/getting-started).

To learn React, check out the [React documentation](https://reactjs.org/).

## Environment Configuration

The application requires a `.env` file in the `api` directory for configuration. Create a file named `.env` with the following variables:

| Variable | Description | Example Value |
|----------|-------------|---------------|
| DATABRICKS_HOST | Your Databricks workspace URL | https://your-workspace.cloud.databricks.com |
| DATABRICKS_TOKEN | Personal access token for authentication | dapi1234567890abcdef |
| DATABRICKS_HTTP_PATH | SQL warehouse HTTP path | /sql/1.0/warehouses/abc123 |
| DATABRICKS_CATALOG | Default catalog to use | main |
| DATABRICKS_SCHEMA | Default schema to use | default |
| FLASK_DEBUG | Enable Flask debug mode | True |
| FLASK_ENV | Flask environment setting | development |

Example `.env` file:

### Backend Setup

The Flask application is configured to run from the project root directory using a `.flaskenv` file. This allows you to run both the frontend and backend from the same directory.

# Unified Catalog Application

A modern web application for managing data catalogs, built with FastAPI and React.

## Prerequisites

- Python 3.8 or higher
- Node.js 14 or higher
- npm 6 or higher
- Hatch (Python build tool)

## Installation

1. Install Hatch:
```bash
pip install hatch
```

2. Install all dependencies:
```bash
npm run install:all
```

This will:
- Install frontend dependencies using npm
- Create a Python virtual environment using Hatch
- Install backend dependencies in the virtual environment

## Development

To run both frontend and backend servers in development mode:

```bash
npm run dev
```

This will:
- Start the React development server on port 3000
- Start the FastAPI development server on port 8000
- Enable hot reloading for both frontend and backend

To run servers separately:

```bash
# Frontend only
npm run dev:frontend

# Backend only
npm run dev:backend
```

## Building for Production

To build both frontend and backend:

```bash
npm run build:all
```

This will:
1. Build the React application
2. Copy the built files to the FastAPI static directory
3. Build the Python package

To build separately:

```bash
# Frontend only
npm run build:frontend

# Backend only
npm run build:backend
```

## Environment Variables

Create a `.env` file in the root directory with the following variables:

```
DATABRICKS_WAREHOUSE_ID=your_warehouse_id
DATABRICKS_HTTP_PATH=your_http_path
DATABRICKS_CATALOG=your_catalog
DATABRICKS_SCHEMA=your_schema
```

## Project Structure

```
ucapp/
├── api/                    # Backend FastAPI application
│   ├── routes/            # API routes
│   ├── models/            # Data models
│   ├── controller/        # Business logic
│   ├── static/           # Static files (frontend build)
│   └── app.py            # Main application file
├── src/                   # Frontend React application
├── public/               # Public assets
├── build.py              # Build script
├── pyproject.toml        # Hatch configuration
├── package.json          # Frontend dependencies
└── README.md            # This file
```

## Contributing

1. Create a new branch for your feature
2. Make your changes
3. Run tests and linting:
```bash
hatch run test
hatch run lint
```
4. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
