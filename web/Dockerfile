# Next.js standalone server. Built in CI (.github/workflows/deploy.yml) and shipped to the server.
FROM node:26-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:26-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Both values are fixed into the build: the /api rewrite target, and the Clerk
# publishable key (public by design, it ships to every browser).
ARG API_URL=http://api:8000
ARG NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
ENV API_URL=$API_URL \
    NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=$NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY \
    NEXT_TELEMETRY_DISABLED=1
RUN test -n "$NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY" || (echo "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY build argument is empty (in CI it comes from the repository secret of that name)" && exit 1)
RUN npm run build

FROM node:26-alpine AS run
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
COPY --from=build --chown=node:node /app/public ./public
USER node
EXPOSE 3000
CMD ["node", "server.js"]
