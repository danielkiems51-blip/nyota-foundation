# Nyota Fund: Project Analysis & Blueprint

## 1. Project Overview
Fuliza Boost is now Nyota Fund, a specialized web application designed to facilitate youth empowerment financing for Safaricom users. It combines a highly polished, brand-aligned UI with a seamless payment integration to provide a premium user experience optimized for mobile growth and social media conversion (TikTok/Instagram).

## 2. Technical Stack
- **Backend:** Django 5.x (Python)
- **Frontend:** HTML5, Tailwind CSS 3.x, Vanilla JavaScript
- **Payment Integration:** PayNexus API (M-Pesa STK Push)
- **Deployment:** Render (PaaS) with WhiteNoise for static files
- **UI Architecture:** Responsive Mobile-First Design (Single Page Application feel via Opaque Modals)

## 3. Core Features & UX Design
- **Safaricom Branding:** Professional green/white palette with a custom dot-pattern background.
- **Dynamic Activity Engine:** Real-time toast notifications simulating live global limit increases to build trust.
- **Micro-interactivity:** Global loaders, button haptics (scaling), and full-screen opaque transitions.
- **Input Neutralization:** Backend-ready phone number normalization (support for `07xx`, `01xx`, `254xx` formats).
- **Legitimacy Architecture:** Security badges, "Safaricom Official" status indicators, and encrypted-flow messaging.

## 4. Systems Blueprint

### A. Data Flow (Payment Initiation)
1. **User Selection:** User selects a limit (e.g., 45k) -> Processing fee calculated (5k).
2. **Identification:** User provides ID and Phone -> Opaque Modal Step 1.
3. **Review:** Confirmation screen with STK Push trigger -> Opaque Modal Step 2.
4. **API Orchestration:** `PayNexusService` normalizes data, authenticates, and sends an STK Push request via PayNexus.
5. **Callback Handling:** PayNexus sends a POST notification to `/api/mpesa/callback/` to update transaction status.

### B. Directory Structure
```text
nyota_fund/
├── nyota_fund/         # Project Settings & Routing
├── nyota/              # Logic App
│   ├── services.py     # PayNexus API Integration Logic
│   ├── views.py        # Landing & Initiation Endpoints
│   └── urls.py         # App-specific Routing
├── templates/          # UI Layer
│   ├── base.html       # Branding, Global CSS, & Activity Engine
│   └── nyota/          # Landing Page & Full-Screen Modals
└── render.yaml         # Infrastructure as Code (Deployment)
```

## 5. Deployment Strategy
- **Infrastructure:** Render Web Services using a `build.sh` script for automated migrations and static collection.
- **Security:** Environment variables for `SECRET_KEY` and PayNexus credentials; `DEBUG=False` in production.

- **Performance:** Minimal external dependencies ensure ultra-fast load times on 3G/4G mobile networks.

