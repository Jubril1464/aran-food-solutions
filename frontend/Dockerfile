# Local development only. docker-compose.yml builds this to run the Vite dev
# server alongside the backend; it is NOT how the frontend is deployed. The
# deployment builds a static bundle with `npm run build` and serves the files
# from Render, with no container involved at all (see render.yaml).
FROM node:22-alpine

WORKDIR /app

# Copied first so `npm ci` is only re-run when the lockfile actually changes.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 5173

# --host binds 0.0.0.0 instead of localhost, without which the port publish
# from docker-compose reaches nothing.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
