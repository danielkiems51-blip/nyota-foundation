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
PAYNEXUS_API_URL=https://paynexus.co.ke
PAYNEXUS_SHOP_EMAIL=your_email@example.com
PAYNEXUS_API_KEY=sk_your_secret_key_from_dashboard
PAYNEXUS_CALLBACK_URL=https://your-app-name.onrender.com/api/mpesa/callback/
```

## 4. Why Render?
*   **Automatic Scaling:** Built-in support for Gunicorn and high traffic.
*   **Static Files:** WhiteNoise is already configured to serve your CSS/JS efficiently.
*   **SSL:** Auto-renewing SSL certificates out of the box.

## 5. PayNexus Setup
1.  Sign in to the [PayNexus Merchant Dashboard](https://paynexus.co.ke).
2.  Generate your `sk_...` API key from the dashboard.
3.  Set `PAYNEXUS_API_KEY` in Render Env Vars to your secret key.
4.  Set `PAYNEXUS_CALLBACK_URL` to your live `.onrender.com` domain to receive payment confirmations.

**API Reference:**
*   **STK Push:** `POST https://paynexus.co.ke/api/mpesa/payment/initiate`
*   **Check Status:** `GET https://paynexus.co.ke/api/payments/{reference}`
*   **Auth Header:** `X-API-Key: sk_...`
