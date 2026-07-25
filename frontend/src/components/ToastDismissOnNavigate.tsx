'use client';

import { useEffect } from 'react';
import { usePathname } from 'next/navigation';
import { toast } from 'sonner';

export default function ToastDismissOnNavigate() {
  const pathname = usePathname();

  useEffect(() => {
    // Automatically clear any active or stale toasts whenever the route changes
    toast.dismiss();
  }, [pathname]);

  return null;
}
