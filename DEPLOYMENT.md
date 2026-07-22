# Nyota Fund Deployment Guide (Render.com)

Follow these steps to deploy your project to Render.

## 1. GitHub Setup
1.  Initialize git: `git init`
2.  Add files: `git add .`
3.  Commit: `git commit -m "chore: prepare for Render.com deployment"`
4.  Push to your GitHub repository.

## 2. Render Deployment
1.  Log in to [Render.com](https://render.com).
2.  Click **New +** and select **Blueprint**.
3.  Connect your GitHub repository.
4.  Render will automatically detect the `render.yaml` file and set up your:
    *   **Web Service** (Nyota Fund)
    *   **Environment Variables**
    *   **Build & Start Commands**

## 3. Environment Variables
In the Render Dashboard, ensure the following variables are set for your Web Service:
```env
DEBUG=False
SECRET_KEY=your_very_secret_key
PAYNEXUS_API_KEY=sk_your_secret_key_here
PAYNEXUS_CALLBACK_URL=https://your-app-name.onrender.com/api/mpesa/callback/
```

## 4. Why Render?
*   **Automatic Scaling:** Built-in support for Gunicorn and high traffic.
*   **Static Files:** WhiteNoise is already configured to serve your CSS/JS efficiently.
*   **SSL:** Auto-renewing SSL certificates out of the box.

## 5. PayNexus Note
Ensure your `PAYNEXUS_CALLBACK_URL` is updated in the Render Env Vars to point to your live `.onrender.com` domain to receive payment confirmations.
