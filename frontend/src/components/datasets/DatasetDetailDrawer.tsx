'use client';

import { Dataset } from '@/types/api';
import {
  Drawer,
  DrawerClose,
  DrawerContent,
  DrawerDescription,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
} from '@/components/ui/drawer';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { format } from 'date-fns';
import Link from 'next/link';

interface DatasetDetailDrawerProps {
  dataset: Dataset | null;
  isOpen: boolean;
  onClose: () => void;
}

function formatBytes(bytes: number, decimals = 2) {
  if (!+bytes) return '0 Bytes';
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
}

export function DatasetDetailDrawer({ dataset, isOpen, onClose }: DatasetDetailDrawerProps) {
  if (!dataset) return null;

  return (
    <Drawer open={isOpen} onOpenChange={onClose}>
      <DrawerContent>
        <div className="mx-auto w-full max-w-sm">
          <DrawerHeader>
            <DrawerTitle className="truncate" title={dataset.original_filename}>
              {dataset.original_filename}
            </DrawerTitle>
            <DrawerDescription>Dataset metadata and details</DrawerDescription>
          </DrawerHeader>
          <div className="p-4 pb-0 space-y-4">
            <div className="flex justify-between items-center">
              <span className="text-sm text-muted-foreground">Status</span>
              {dataset.status === 'completed' && (
                <Badge className="bg-emerald-500/15 text-emerald-600 border-emerald-500/20 hover:bg-emerald-500/15 font-medium" variant="outline">
                  completed
                </Badge>
              )}
              {(dataset.status === 'profiling' || dataset.status === 'pending') && (
                <Badge className="bg-blue-500/15 text-blue-600 border-blue-500/20 animate-pulse hover:bg-blue-500/15 font-medium" variant="outline">
                  {dataset.status}
                </Badge>
              )}
              {dataset.status === 'failed' && (
                <Badge className="bg-destructive/15 text-destructive border-destructive/20 hover:bg-destructive/15 font-medium" variant="outline">
                  failed
                </Badge>
              )}
              {dataset.status === 'uploaded' && (
                <Badge className="bg-muted text-muted-foreground hover:bg-muted font-medium" variant="outline">
                  uploaded
                </Badge>
              )}
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-muted-foreground">Size</span>
              <span className="text-sm font-medium">{formatBytes(dataset.file_size)}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-muted-foreground">Extension</span>
              <span className="text-sm font-medium">{dataset.extension}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-muted-foreground">MIME Type</span>
              <span className="text-sm font-medium truncate max-w-[200px]" title={dataset.mime_type}>
                {dataset.mime_type}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-muted-foreground">Uploaded At</span>
              <span className="text-sm font-medium">
                {format(new Date(dataset.created_at), 'MMM d, yyyy HH:mm')}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-muted-foreground">Dataset ID</span>
              <span className="text-xs font-mono text-muted-foreground truncate max-w-[200px]" title={dataset.uuid}>
                {dataset.uuid}
              </span>
            </div>
            {dataset.status === 'failed' && dataset.error_message && (
              <div className="flex flex-col gap-1 mt-2">
                <span className="text-sm text-destructive font-medium">Error Details</span>
                <span className="text-xs text-muted-foreground bg-destructive/10 p-2 rounded-md border border-destructive/20">
                  {dataset.error_message}
                </span>
              </div>
            )}
          </div>
          <DrawerFooter className="flex flex-col gap-2 pt-4">
            {dataset.status === 'completed' && (
              <Button asChild className="w-full" onClick={onClose}>
                <Link href={`/datasets/${dataset.uuid}/profile`}>
                  View Dataset Profile
                </Link>
              </Button>
            )}
            {dataset.status === 'uploaded' && (
              <Button asChild className="w-full" onClick={onClose}>
                <Link href={`/datasets/${dataset.uuid}/profile`}>
                  Analyze Dataset
                </Link>
              </Button>
            )}
            {(dataset.status === 'pending' || dataset.status === 'profiling') && (
              <Button disabled className="w-full">
                Analyzing...
              </Button>
            )}
            {dataset.status === 'failed' && (
              <Button asChild variant="destructive" className="w-full" onClick={onClose}>
                <Link href={`/datasets/${dataset.uuid}/profile`}>
                  Analyze Again
                </Link>
              </Button>
            )}
            <DrawerClose asChild>
              <Button variant="outline" className="w-full">Close</Button>
            </DrawerClose>
          </DrawerFooter>
        </div>
      </DrawerContent>
    </Drawer>
  );
}
