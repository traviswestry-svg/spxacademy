# Render Frontend Deploy Fix

Use these settings for the Static Site frontend:

- Root Directory: `frontend`
- Build Command: `corepack enable && corepack prepare pnpm@9.12.3 --activate && pnpm install --no-frozen-lockfile && pnpm run build`
- Publish Directory: `dist`
- Environment Variable: `NODE_VERSION=20.19.5`

Do not upload `node_modules` or `dist` to GitHub.
