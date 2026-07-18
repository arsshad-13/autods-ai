'use client';

import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/lib/store';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

export default function ProfilePage() {
  const router = useRouter();
  const { user, logout } = useAuthStore();

  const handleLogout = () => {
    logout();
    router.push('/login');
  };

  if (!user) {
    return null; // Handled by ProtectedRoute
  }

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-50 p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Profile</CardTitle>
          <CardDescription>Welcome back to AutoDS AI.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <p className="text-sm font-medium text-gray-500">Name</p>
            <p className="text-base">{user.name}</p>
          </div>
          <div>
            <p className="text-sm font-medium text-gray-500">Email</p>
            <p className="text-base">{user.email}</p>
          </div>
          <div>
            <p className="text-sm font-medium text-gray-500">User ID</p>
            <p className="text-xs text-gray-400 break-all">{user.uuid}</p>
          </div>
          <div>
            <p className="text-sm font-medium text-gray-500">Joined</p>
            <p className="text-base">{new Date(user.created_at).toLocaleDateString()}</p>
          </div>
          <Button onClick={handleLogout} variant="destructive" className="w-full mt-4">
            Logout
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
