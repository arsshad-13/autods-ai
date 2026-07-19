'use client';

import { useState, useEffect, useCallback } from 'react';
import { Dataset } from '@/types/api';
import { listDatasets, uploadDataset, deleteDataset } from '@/lib/api';
import { DropZone } from '@/components/datasets/DropZone';
import { DatasetTable } from '@/components/datasets/DatasetTable';
import { DatasetDetailDrawer } from '@/components/datasets/DatasetDetailDrawer';
import { DeleteConfirmDialog } from '@/components/datasets/DeleteConfirmDialog';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { ChevronLeft, ChevronRight, Loader2 } from 'lucide-react';

export default function DatasetsPage() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [isLoading, setIsLoading] = useState(true);
  
  // Upload state
  const [isUploading, setIsUploading] = useState(false);
  
  // Drawer state
  const [selectedDataset, setSelectedDataset] = useState<Dataset | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  
  // Delete dialog state
  const [datasetToDelete, setDatasetToDelete] = useState<Dataset | null>(null);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const fetchDatasets = useCallback(async (currentPage: number) => {
    setIsLoading(true);
    try {
      const response = await listDatasets(currentPage, pageSize);
      setDatasets(response.items);
      setTotal(response.total);
    } catch (error: any) {
      toast.error(error.message || 'Failed to load datasets');
    } finally {
      setIsLoading(false);
    }
  }, [pageSize]);

  useEffect(() => {
    fetchDatasets(page);
  }, [page, fetchDatasets]);

  const handleUpload = async (file: File) => {
    setIsUploading(true);
    try {
      await uploadDataset(file);
      toast.success('Dataset uploaded successfully');
      // Refresh to page 1 to see the new upload
      if (page === 1) {
        await fetchDatasets(1);
      } else {
        setPage(1);
      }
    } catch (error: any) {
      toast.error(error.message || 'Failed to upload dataset');
    } finally {
      setIsUploading(false);
    }
  };

  const handleViewDetails = (dataset: Dataset) => {
    setSelectedDataset(dataset);
    setIsDrawerOpen(true);
  };

  const handleDeleteClick = (dataset: Dataset) => {
    setDatasetToDelete(dataset);
    setIsDeleteDialogOpen(true);
  };

  const confirmDelete = async (uuid: string) => {
    setIsDeleting(true);
    try {
      await deleteDataset(uuid);
      toast.success('Dataset deleted successfully');
      setIsDeleteDialogOpen(false);
      setDatasetToDelete(null);
      
      // If we deleted the last item on the page, and we're not on page 1, go back a page
      if (datasets.length === 1 && page > 1) {
        setPage(page - 1);
      } else {
        await fetchDatasets(page);
      }
    } catch (error: any) {
      toast.error(error.message || 'Failed to delete dataset');
    } finally {
      setIsDeleting(false);
    }
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="container mx-auto py-8 max-w-5xl space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Datasets</h1>
        <p className="text-muted-foreground mt-2">
          Upload and manage your datasets for analysis.
        </p>
      </div>

      <div className="bg-card rounded-xl border shadow-sm p-6">
        <h2 className="text-xl font-semibold mb-4">Upload New Dataset</h2>
        <DropZone onUpload={handleUpload} isUploading={isUploading} />
      </div>

      <div className="space-y-4">
        <h2 className="text-xl font-semibold">Your Datasets</h2>
        
        {isLoading ? (
          <div className="flex justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <DatasetTable 
            datasets={datasets} 
            onViewDetails={handleViewDetails}
            onDelete={handleDeleteClick}
          />
        )}

        {!isLoading && total > 0 && (
          <div className="flex items-center justify-between pt-4">
            <div className="text-sm text-muted-foreground">
              Showing {((page - 1) * pageSize) + 1} to {Math.min(page * pageSize, total)} of {total} datasets
            </div>
            <div className="flex space-x-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
              >
                <ChevronLeft className="h-4 w-4 mr-1" />
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
              >
                Next
                <ChevronRight className="h-4 w-4 ml-1" />
              </Button>
            </div>
          </div>
        )}
      </div>

      <DatasetDetailDrawer
        dataset={selectedDataset}
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
      />

      <DeleteConfirmDialog
        dataset={datasetToDelete}
        isOpen={isDeleteDialogOpen}
        onClose={() => setIsDeleteDialogOpen(false)}
        onConfirm={confirmDelete}
        isDeleting={isDeleting}
      />
    </div>
  );
}
