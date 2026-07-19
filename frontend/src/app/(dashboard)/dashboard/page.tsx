'use client';

import { useEffect, useState } from 'react';
import { useAuthStore } from '@/lib/store';
import { listDatasets } from '@/lib/api';
import { Dataset } from '@/types/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { 
  Database, 
  FileUp, 
  BrainCircuit, 
  BarChart, 
  HardDrive, 
  Clock, 
  FileText 
} from 'lucide-react';
import Link from 'next/link';

export default function DashboardPage() {
  const { user } = useAuthStore();
  const [stats, setStats] = useState({
    totalDatasets: 0,
    totalFiles: 0,
    storageUsed: 0,
    lastUploadTime: null as string | null,
    isLoading: true
  });

  useEffect(() => {
    async function loadStats() {
      try {
        // Fetch first page to get total count and recent items
        const res = await listDatasets(1, 50);
        
        const storage = res.items.reduce((acc: number, item: Dataset) => acc + (item.file_size || 0), 0);
        const lastUpload = res.items.length > 0 
          ? [...res.items].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())[0].created_at 
          : null;

        setStats({
          totalDatasets: res.total,
          totalFiles: res.total, // Currently 1 dataset = 1 file
          storageUsed: storage,
          lastUploadTime: lastUpload,
          isLoading: false
        });
      } catch (error) {
        console.error("Failed to load datasets for stats", error);
        setStats(s => ({ ...s, isLoading: false }));
      }
    }
    
    loadStats();
  }, []);

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'Never';
    const date = new Date(dateString);
    return new Intl.RelativeTimeFormat('en', { numeric: 'auto' }).format(
      Math.ceil((date.getTime() - Date.now()) / (1000 * 60 * 60 * 24)),
      'day'
    );
  };

  return (
    <div className="flex-1 space-y-6 p-8 pt-6">
      <div className="flex items-center justify-between space-y-2">
        <h2 className="text-3xl font-bold tracking-tight">Dashboard</h2>
      </div>
      
      <div className="mb-8">
        <h3 className="text-xl font-medium">Welcome back, {user?.name || 'Data Scientist'}! 👋</h3>
        <p className="text-muted-foreground mt-1">
          Here is an overview of your workspace and recent activities.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card className="shadow-sm">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Datasets</CardTitle>
            <Database className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {stats.isLoading ? '...' : stats.totalDatasets}
            </div>
          </CardContent>
        </Card>
        <Card className="shadow-sm">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Files</CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {stats.isLoading ? '...' : stats.totalFiles}
            </div>
          </CardContent>
        </Card>
        <Card className="shadow-sm">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Storage Used</CardTitle>
            <HardDrive className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {stats.isLoading ? '...' : formatBytes(stats.storageUsed)}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Estimated from recent uploads
            </p>
          </CardContent>
        </Card>
        <Card className="shadow-sm">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Last Upload</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {stats.isLoading ? '...' : formatDate(stats.lastUploadTime)}
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-7 mt-8">
        <Card className="col-span-4 shadow-sm">
          <CardHeader>
            <CardTitle>Quick Actions</CardTitle>
            <CardDescription>Get started with your data science workflow.</CardDescription>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-4">
            <Link href="/datasets" className="group">
              <div className="border rounded-lg p-6 flex flex-col items-center justify-center text-center hover:bg-accent transition-colors h-full">
                <div className="h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                  <Database className="h-6 w-6 text-primary" />
                </div>
                <h3 className="font-semibold mb-1">Manage Datasets</h3>
                <p className="text-xs text-muted-foreground">Upload and prepare your data</p>
              </div>
            </Link>
            
            <div className="border rounded-lg p-6 flex flex-col items-center justify-center text-center opacity-60 cursor-not-allowed">
              <div className="h-12 w-12 rounded-full bg-muted flex items-center justify-center mb-4">
                <BrainCircuit className="h-6 w-6 text-muted-foreground" />
              </div>
              <h3 className="font-semibold mb-1">Train Models</h3>
              <p className="text-xs text-muted-foreground">Coming soon in AutoML phase</p>
            </div>
            
            <div className="border rounded-lg p-6 flex flex-col items-center justify-center text-center opacity-60 cursor-not-allowed">
              <div className="h-12 w-12 rounded-full bg-muted flex items-center justify-center mb-4">
                <BarChart className="h-6 w-6 text-muted-foreground" />
              </div>
              <h3 className="font-semibold mb-1">View Reports</h3>
              <p className="text-xs text-muted-foreground">Coming soon in Explainability phase</p>
            </div>
            
            <div className="border rounded-lg p-6 flex flex-col items-center justify-center text-center opacity-60 cursor-not-allowed">
              <div className="h-12 w-12 rounded-full bg-muted flex items-center justify-center mb-4">
                <FileUp className="h-6 w-6 text-muted-foreground" />
              </div>
              <h3 className="font-semibold mb-1">Deploy Endpoint</h3>
              <p className="text-xs text-muted-foreground">Coming soon in Deployment phase</p>
            </div>
          </CardContent>
        </Card>

        <Card className="col-span-3 shadow-sm flex flex-col">
          <CardHeader>
            <CardTitle>Recent Activity</CardTitle>
            <CardDescription>Your latest actions across the platform.</CardDescription>
          </CardHeader>
          <CardContent className="flex-1 flex items-center justify-center p-6 border-t">
            <div className="text-center">
              <div className="bg-muted h-12 w-12 rounded-full flex items-center justify-center mx-auto mb-3">
                <Clock className="h-6 w-6 text-muted-foreground" />
              </div>
              <h3 className="font-medium text-muted-foreground">No recent activity</h3>
              <p className="text-sm text-muted-foreground/70 mt-1">Upload a dataset to see activity here.</p>
              <Button asChild variant="outline" className="mt-4">
                <Link href="/datasets">Go to Datasets</Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
