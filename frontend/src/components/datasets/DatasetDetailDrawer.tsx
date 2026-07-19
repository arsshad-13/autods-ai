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
              <Badge variant={dataset.status === 'uploaded' ? 'default' : 'secondary'}>
                {dataset.status}
              </Badge>
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
          </div>
          <DrawerFooter>
            <DrawerClose asChild>
              <Button variant="outline">Close</Button>
            </DrawerClose>
          </DrawerFooter>
        </div>
      </DrawerContent>
    </Drawer>
  );
}
