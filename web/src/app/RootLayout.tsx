import { Outlet } from 'react-router-dom';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';

// Top-level route layout: drives the dynamic document title from the active
// route and renders the matched child route via <Outlet />.
export default function RootLayout() {
  useDocumentTitle();
  return <Outlet />;
}
