'use client';

import { useCallback, useState } from 'react';
import { useDropzone, FileRejection } from 'react-dropzone';
import { UploadCloud, File, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';

interface DropZoneProps {
  onUpload: (file: File) => Promise<void>;
  isUploading: boolean;
}

const MAX_SIZE = 100 * 1024 * 1024; // 100 MB

export function DropZone({ onUpload, isUploading }: DropZoneProps) {
  const onDrop = useCallback(
    async (acceptedFiles: File[], fileRejections: FileRejection[]) => {
      if (fileRejections.length > 0) {
        const error = fileRejections[0]?.errors[0];
        toast.error(error?.message || 'Invalid file uploaded');
        return;
      }

      if (acceptedFiles.length > 0) {
        try {
          await onUpload(acceptedFiles[0]);
        } catch (error: any) {
          toast.error(error.message || 'Upload failed');
        }
      }
    },
    [onUpload]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    maxFiles: 1,
    maxSize: MAX_SIZE,
    accept: {
      'text/csv': ['.csv'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'application/vnd.ms-excel': ['.xls'],
    },
    disabled: isUploading,
  });

  return (
    <div
      {...getRootProps()}
      className={cn(
        'border-2 border-dashed rounded-lg p-12 text-center cursor-pointer transition-colors flex flex-col items-center justify-center',
        isDragActive ? 'border-primary bg-primary/5' : 'border-muted-foreground/25 hover:border-primary/50',
        isUploading && 'opacity-50 cursor-not-allowed'
      )}
    >
      <input {...getInputProps()} />
      <UploadCloud className="h-10 w-10 text-muted-foreground mb-4" />
      {isUploading ? (
        <p className="text-sm text-muted-foreground">Uploading dataset...</p>
      ) : isDragActive ? (
        <p className="text-sm font-medium">Drop the dataset here...</p>
      ) : (
        <div className="space-y-1">
          <p className="text-sm font-medium">Drag & drop a dataset here, or click to select</p>
          <p className="text-xs text-muted-foreground">
            Supports .csv, .xlsx, .xls up to 100MB
          </p>
        </div>
      )}
    </div>
  );
}
