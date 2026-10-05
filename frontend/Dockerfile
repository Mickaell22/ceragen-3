# Build: Vite incrusta VITE_API_URL en el JS, por eso entra como build arg.
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-fund --no-audit
COPY . .
ARG VITE_API_URL
RUN test -n "$VITE_API_URL" || (echo "falta VITE_API_URL" && exit 1)
RUN npm run build

# Runtime: nginx sin root sirviendo los estáticos.
FROM nginxinc/nginx-unprivileged:alpine
# Railway inyecta PORT; en local lo fija docker-compose.
ENV PORT=8080
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
