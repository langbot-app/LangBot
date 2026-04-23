import React, { Suspense } from 'react';
import { createBrowserRouter, Navigate } from 'react-router-dom';

// Layouts
import LoginLayout from '@/app/login/layout';
import RegisterLayout from '@/app/register/layout';
import ResetPasswordLayout from '@/app/reset-password/layout';
import HomeLayout from '@/app/home/layout';

// Pages
import LoginPage from '@/app/login/page';
import RegisterPage from '@/app/register/page';
import ResetPasswordPage from '@/app/reset-password/page';
import WizardPage from '@/app/wizard/page';
import SpaceCallbackPage from '@/app/auth/space/callback/page';
import HomePage from '@/app/home/page';
import MonitoringPage from '@/app/home/monitoring/page';
import BotsPage from '@/app/home/bots/page';
import PipelinesPage from '@/app/home/pipelines/page';
import PluginsPage from '@/app/home/plugins/page';
import MarketPage from '@/app/home/market/page';
import MCPPage from '@/app/home/mcp/page';
import KnowledgePage from '@/app/home/knowledge/page';

const Loading = () => <div>Loading...</div>;

export const router = createBrowserRouter([
  {
    path: '/',
    element: <Navigate to="/login" replace />,
  },
  {
    path: '/login',
    element: (
      <LoginLayout>
        <LoginPage />
      </LoginLayout>
    ),
  },
  {
    path: '/register',
    element: (
      <RegisterLayout>
        <RegisterPage />
      </RegisterLayout>
    ),
  },
  {
    path: '/reset-password',
    element: (
      <ResetPasswordLayout>
        <ResetPasswordPage />
      </ResetPasswordLayout>
    ),
  },
  {
    path: '/wizard',
    element: <WizardPage />,
  },
  {
    path: '/auth/space/callback',
    element: <SpaceCallbackPage />,
  },
  {
    path: '/home',
    element: (
      <Suspense fallback={<Loading />}>
        <HomeLayout>
          <HomePage />
        </HomeLayout>
      </Suspense>
    ),
  },
  {
    path: '/home/monitoring',
    element: (
      <Suspense fallback={<Loading />}>
        <HomeLayout>
          <MonitoringPage />
        </HomeLayout>
      </Suspense>
    ),
  },
  {
    path: '/home/bots',
    element: (
      <Suspense fallback={<Loading />}>
        <HomeLayout>
          <BotsPage />
        </HomeLayout>
      </Suspense>
    ),
  },
  {
    path: '/home/pipelines',
    element: (
      <Suspense fallback={<Loading />}>
        <HomeLayout>
          <PipelinesPage />
        </HomeLayout>
      </Suspense>
    ),
  },
  {
    path: '/home/plugins',
    element: (
      <Suspense fallback={<Loading />}>
        <HomeLayout>
          <PluginsPage />
        </HomeLayout>
      </Suspense>
    ),
  },
  {
    path: '/home/market',
    element: (
      <Suspense fallback={<Loading />}>
        <HomeLayout>
          <MarketPage />
        </HomeLayout>
      </Suspense>
    ),
  },
  {
    path: '/home/mcp',
    element: (
      <Suspense fallback={<Loading />}>
        <HomeLayout>
          <MCPPage />
        </HomeLayout>
      </Suspense>
    ),
  },
  {
    path: '/home/knowledge',
    element: (
      <Suspense fallback={<Loading />}>
        <HomeLayout>
          <KnowledgePage />
        </HomeLayout>
      </Suspense>
    ),
  },
]);
