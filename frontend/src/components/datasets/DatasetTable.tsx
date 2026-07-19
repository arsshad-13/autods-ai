'use client';

import { Dataset } from '@/types/api';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Eye, Trash2, FileSpreadsheet } from 'lucide-react';
import { format } from 'date-fns';

interface DatasetTableProps {
  datasets: Dataset[];
  onViewDetails: (dataset: Dataset) => void;
  onDelete: (dataset: Dataset) => void;
}

function formatBytes(bytes: number, decimals = 2) {
  if (!+bytes) return '0 Bytes';
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
}

export function DatasetTable({ datasets, onViewDetails, onDelete }: DatasetTableProps) {
  if (datasets.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center p-12 text-center border rounded-lg border-dashed bg-muted/10">
        <FileSpreadsheet className="h-12 w-12 text-muted-foreground mb-4" />
        <h3 className="text-lg font-medium">No datasets uploaded</h3>
        <p className="text-sm text-muted-foreground mt-1">
          Upload your first dataset to get started with analysis.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Filename</TableHead>
            <TableHead>Size</TableHead>
            <TableHead>Uploaded</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {datasets.map((dataset) => (
            <TableRow key={dataset.uuid}>
              <TableCell className="font-medium">
                <div className="flex items-center space-x-2">
                  <FileSpreadsheet className="h-4 w-4 text-muted-foreground" />
                  <span className="truncate max-w-[200px]" title={dataset.original_filename}>
                    {dataset.original_filename}
                  </span>
                </div>
              </TableCell>
              <TableCell>{formatBytes(dataset.file_size)}</TableCell>
              <TableCell>{format(new Date(dataset.created_at), 'MMM d, yyyy')}</TableCell>
              <TableCell>
                <Badge variant={dataset.status === 'uploaded' ? 'default' : 'secondary'}>
                  {dataset.status}
                </Badge>
              </TableCell>
              <TableCell className="text-right">
                <div className="flex justify-end space-x-2">
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => onViewDetails(dataset)}
                    title="View Details"
                  >
                    <Eye className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="text-destructive hover:text-destructive hover:bg-destructive/10"
                    onClick={() => onDelete(dataset)}
                    title="Delete"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
