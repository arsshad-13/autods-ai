import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'AutoDS AI',
  description: 'Autonomous Data Scientist Platform',
};

import ProtectedRoute from '@/components/ProtectedRoute';

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <ProtectedRoute>
          {children}
        </ProtectedRoute>
      </body>
    </html>
  );
}
