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
import { ChevronLeft, ChevronRight, Loader2, Database, Upload } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

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

  // Dismiss all stale toasts immediately when this page mounts to prevent cross-page leakage
  useEffect(() => {
    toast.dismiss();
  }, []);

  useEffect(() => {
    fetchDatasets(page);
  }, [page, fetchDatasets]);

  // Re-fetch silently when the user returns to this tab/page (e.g. navigating back from
  // the profile page) so the status badge always reflects the latest backend state.
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        fetchDatasets(page);
      }
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [page, fetchDatasets]);


  const handleUpload = async (file: File) => {
    setIsUploading(true);
    try {
      await uploadDataset(file);
      toast.success('Dataset uploaded successfully', { duration: 2500 });
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
    <div className="flex-1 space-y-6 p-8 pt-6">
      <div className="flex flex-col space-y-2">
        <h2 className="text-3xl font-bold tracking-tight flex items-center gap-2">
          <Database className="h-8 w-8 text-primary" />
          Datasets
        </h2>
        <p className="text-muted-foreground">
          Upload and manage your datasets for analysis and model training.
        </p>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Upload Section */}
        <Card className="xl:col-span-1 shadow-sm h-fit">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Upload className="h-5 w-5" />
              Upload New Dataset
            </CardTitle>
            <CardDescription>
              Drag and drop your CSV or Excel files here.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <DropZone onUpload={handleUpload} isUploading={isUploading} />
          </CardContent>
        </Card>

        {/* Datasets Table Section */}
        <Card className="xl:col-span-2 shadow-sm">
          <CardHeader>
            <CardTitle>Your Datasets</CardTitle>
            <CardDescription>
              Manage existing datasets and view their details.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="flex justify-center items-center py-20">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : (
              <div className="space-y-4">
                <DatasetTable 
                  datasets={datasets} 
                  onViewDetails={handleViewDetails}
                  onDelete={handleDeleteClick}
                />

                {total > 0 && (
                  <div className="flex flex-col sm:flex-row items-center justify-between pt-4 border-t gap-4">
                    <div className="text-sm text-muted-foreground">
                      Showing <span className="font-medium text-foreground">{((page - 1) * pageSize) + 1}</span> to <span className="font-medium text-foreground">{Math.min(page * pageSize, total)}</span> of <span className="font-medium text-foreground">{total}</span> datasets
                    </div>
                    <div className="flex space-x-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setPage((p) => Math.max(1, p - 1))}
                        disabled={page === 1}
                        className="h-8"
                      >
                        <ChevronLeft className="h-4 w-4 mr-1" />
                        Previous
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                        disabled={page >= totalPages}
                        className="h-8"
                      >
                        Next
                        <ChevronRight className="h-4 w-4 ml-1" />
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
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
