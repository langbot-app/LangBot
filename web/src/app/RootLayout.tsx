import { Outlet } from 'react-router-dom';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import { BetaBanner } from '@/components/BetaBanner';

// Top-level route layout: drives the dynamic document title from the active
// route and renders the matched child route via <Outlet />.
export default function RootLayout() {
  useDocumentTitle();
  return (
    <>
      <BetaBanner />
      <Outlet />
    </>
  );
}
