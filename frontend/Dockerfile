# Development Dockerfile
FROM node:20-alpine

RUN apk add --no-cache libc6-compat
# Install pnpm
RUN corepack enable && corepack prepare pnpm@latest --activate
WORKDIR /app

# Copy package files
COPY package.json pnpm-lock.yaml* ./
RUN pnpm install --frozen-lockfile || pnpm install

# Copy application code
COPY . .

EXPOSE 3000

ENV NEXT_TELEMETRY_DISABLED 1

CMD ["pnpm", "run", "dev"]

