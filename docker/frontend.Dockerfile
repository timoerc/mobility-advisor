# Mobility Advisor frontend: Vite build served by nginx.
#
# frontend/dist/ is gitignored, so the build must happen in-image, not be copied from
# the host. Node tag matches the local dev toolchain (v22); package.json declares no
# engines field.
FROM node:22-alpine AS build
WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
# `build` runs `tsc && vite build` — a type error fails this step, which is intentional.
RUN npm run build

FROM nginx:1.27-alpine
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/frontend/dist /usr/share/nginx/html

EXPOSE 80
