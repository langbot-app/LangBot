import React, { Suspense } from 'react';
import { createBrowserRouter, Navigate } from 'react-router-dom';

// Layouts
import LoginLayout from '@/app/login/layout';
import RegisterLayout from '@/app/register/layout';
import ResetPasswordLayout from '@/app/reset-password/layout';

// Pages
import LoginPage from '@/app/login/page';
import RegisterPage from '@/app/register/page';
import ResetPasswordPage from '@/app/reset-password/page';
import SpaceCallbackPage from '@/app/auth/space/callback/page';
import ErrorPage from '@/components/ErrorPage';
import BackendUnavailablePage from '@/components/BackendUnavailablePage';
import RootLayout from '@/app/RootLayout';
import AcceptInvitationPage from '@/app/invitations/accept/page';
import WorkspaceSelectPage from '@/app/workspaces/select/page';

const HomeLayout = React.lazy(() => import('@/app/home/layout'));
const WizardPage = React.lazy(() => import('@/app/wizard/page'));
const HomePage = React.lazy(() => import('@/app/home/page'));
const MonitoringPage = React.lazy(() => import('@/app/home/monitoring/page'));
const BotsPage = React.lazy(() => import('@/app/home/bots/page'));
const AgentsPage = React.lazy(() => import('@/app/home/agents/page'));
const PipelinesPage = React.lazy(() => import('@/app/home/pipelines/page'));
const PluginsPage = React.lazy(() => import('@/app/home/plugins/page'));
const AddExtensionPage = React.lazy(
  () => import('@/app/home/add-extension/page'),
);
const MCPPage = React.lazy(() => import('@/app/home/mcp/page'));
const KnowledgePage = React.lazy(() => import('@/app/home/knowledge/page'));
const SkillsPage = React.lazy(() => import('@/app/home/skills/page'));
const PluginPagesPage = React.lazy(
  () => import('@/app/home/plugin-pages/page'),
);

const Loading = () => <div>Loading...</div>;

export const router = createBrowserRouter([
  {
    element: <RootLayout />,
    errorElement: <ErrorPage />,
    children: [
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
        path: '/invitations/accept',
        element: <AcceptInvitationPage />,
      },
      {
        path: '/workspaces/select',
        element: <WorkspaceSelectPage />,
      },
      {
        path: '/wizard',
        element: (
          <Suspense fallback={<Loading />}>
            <WizardPage />
          </Suspense>
        ),
      },
      {
        path: '/backend-unavailable',
        element: <BackendUnavailablePage />,
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
        path: '/home/agents',
        element: (
          <Suspense fallback={<Loading />}>
            <HomeLayout>
              <AgentsPage />
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
        path: '/home/extensions',
        element: (
          <Suspense fallback={<Loading />}>
            <HomeLayout>
              <PluginsPage />
            </HomeLayout>
          </Suspense>
        ),
      },
      {
        path: '/home/add-extension',
        element: (
          <Suspense fallback={<Loading />}>
            <HomeLayout>
              <AddExtensionPage />
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
      {
        path: '/home/skills',
        element: (
          <Suspense fallback={<Loading />}>
            <HomeLayout>
              <SkillsPage />
            </HomeLayout>
          </Suspense>
        ),
      },
      {
        path: '/home/plugin-pages',
        element: (
          <Suspense fallback={<Loading />}>
            <HomeLayout>
              <PluginPagesPage />
            </HomeLayout>
          </Suspense>
        ),
      },
    ],
  },
]);
