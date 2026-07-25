'use client';

import { useState, useEffect, Fragment } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { getDataset, getDatasetProfile, generateDatasetProfile } from '@/lib/api';
import { Dataset, DatasetProfile, ColumnProfile } from '@/types/api';
import { toast } from 'sonner';
import {
  ArrowLeft,
  Database,
  Search,
  AlertCircle,
  CheckCircle2,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  Loader2,
  Sparkles,
  RefreshCw,
  Eye,
  Info,
  Calendar,
  Binary,
  Hash,
  Type,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

function formatBytes(bytes: number, decimals = 2) {
  if (!+bytes) return '0 Bytes';
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
}

export default function DatasetProfilePage() {
  const params = useParams();
  const router = useRouter();
  const uuid = params.uuid as string;

  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [profile, setProfile] = useState<DatasetProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isProfiling, setIsProfiling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState<'overview' | 'columns' | 'preview' | 'recommendations'>('overview');
  const [expandedColumn, setExpandedColumn] = useState<string | null>(null);

  // Dismiss all stale toasts immediately when this page mounts to prevent cross-page leakage
  useEffect(() => {
    toast.dismiss();
  }, []);

  // Effect 1: Initial mount data load
  useEffect(() => {
    let active = true;

    const loadData = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const ds = await getDataset(uuid);
        if (!active) return;
        setDataset(ds);

        if (ds.status === 'completed') {
          const prof = await getDatasetProfile(uuid);
          if (!active) return;
          setProfile(prof);
        }
      } catch (err: any) {
        if (!active) return;
        if (err.message?.includes('404') || err.message?.includes('not found') || err.message?.includes('Profile not found')) {
          // Profile not yet generated, which is expected for unanalyzed uploads
        } else {
          setError(err.message || 'Failed to load dataset details');
        }
      } finally {
        if (active) {
          setIsLoading(false);
        }
      }
    };

    loadData();

    return () => {
      active = false;
    };
  }, [uuid]);

  // Effect 2: Status polling when profiling is active
  useEffect(() => {
    if (!uuid || !dataset) return;

    const status = dataset.status;
    if (status !== 'pending' && status !== 'profiling') {
      setIsProfiling(false);
      return;
    }

    setIsProfiling(true);
    let active = true;

    const poll = async () => {
      try {
        const ds = await getDataset(uuid);
        if (!active) return;
        setDataset(ds);

        if (ds.status === 'completed') {
          const prof = await getDatasetProfile(uuid);
          if (!active) return;
          setProfile(prof);
          setIsProfiling(false);
          toast.dismiss();
          toast.success('Dataset analyzed successfully.');
        } else if (ds.status === 'failed') {
          setIsProfiling(false);
          toast.dismiss();
          toast.error('Dataset analysis failed.');
        }
      } catch (err) {
        console.error("Error polling profiling status:", err);
      }
    };

    // Poll status every 2 seconds
    const interval = setInterval(poll, 2000);

    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [uuid, dataset?.status]);

  const handleAnalyze = async () => {
    setIsProfiling(true);
    setError(null);
    toast.dismiss(); // Cleanly dismiss any active upload or stale toasts
    try {
      const updatedDs = await generateDatasetProfile(uuid);
      setDataset(updatedDs);
      toast.success('Dataset analysis started.');
    } catch (err: any) {
      toast.error(err.message || 'Failed to start analysis');
      setIsProfiling(false);
    }
  };

  const getQualityBadgeColor = (level: string) => {
    switch (level) {
      case 'Excellent':
        return 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20';
      case 'Good':
        return 'bg-blue-500/10 text-blue-500 border-blue-500/20';
      case 'Fair':
        return 'bg-amber-500/10 text-amber-500 border-amber-500/20';
      case 'Poor':
        return 'bg-destructive/10 text-destructive border-destructive/20';
      default:
        return 'bg-muted text-muted-foreground';
    }
  };

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'numeric':
        return <Hash className="h-4 w-4 text-blue-500" />;
      case 'categorical':
        return <Type className="h-4 w-4 text-indigo-500" />;
      case 'boolean':
        return <Binary className="h-4 w-4 text-emerald-500" />;
      case 'datetime':
        return <Calendar className="h-4 w-4 text-amber-500" />;
      default:
        return <Info className="h-4 w-4 text-muted-foreground" />;
    }
  };

  if (isLoading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center min-h-[400px] gap-4">
        <Loader2 className="h-10 w-10 animate-spin text-primary" />
        <p className="text-muted-foreground text-sm font-medium">Loading dataset details...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 p-8 max-w-4xl mx-auto space-y-6">
        <Button variant="ghost" onClick={() => { router.push('/datasets'); router.refresh(); }} className="gap-2">
          <ArrowLeft className="h-4 w-4" /> Back to Datasets
        </Button>
        <Card className="border-destructive/30 bg-destructive/5">
          <CardHeader className="flex flex-row items-center gap-4">
            <AlertCircle className="h-8 w-8 text-destructive" />
            <div>
              <CardTitle>Error Loading Profile</CardTitle>
              <CardDescription className="text-destructive/80 mt-1">{error}</CardDescription>
            </div>
          </CardHeader>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex-1 space-y-6 p-8 pt-6">
      {/* Top Breadcrumb & Action Row */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Button variant="outline" size="icon" onClick={() => { router.push('/datasets'); router.refresh(); }}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h2 className="text-3xl font-bold tracking-tight flex items-center gap-2">
              <Database className="h-8 w-8 text-primary" />
              {dataset?.original_filename}
            </h2>
            <p className="text-sm text-muted-foreground mt-0.5">
              Dataset Profile & Quality Assessment Report
            </p>
          </div>
        </div>

        {dataset && (
          <Button
            onClick={handleAnalyze}
            className="gap-2"
            disabled={isProfiling || dataset.status === 'pending' || dataset.status === 'profiling'}
          >
            {isProfiling || dataset.status === 'pending' || dataset.status === 'profiling' ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            {isProfiling || dataset.status === 'pending' || dataset.status === 'profiling'
              ? 'Analyzing Dataset...'
              : profile
              ? 'Re-analyze Dataset'
              : 'Analyze Dataset'}
          </Button>
        )}
      </div>

      {/* 1. Asynchronous Profiling Loading State */}
      {isProfiling && (
        <Card className="border-primary/20 bg-primary/5 overflow-hidden">
          <CardHeader className="text-center py-10 space-y-4">
            <Loader2 className="h-12 w-12 animate-spin text-primary mx-auto" />
            <div className="space-y-1">
              <CardTitle className="text-xl">Analyzing Dataset...</CardTitle>
              <CardDescription className="max-w-md mx-auto text-sm">
                Our Profiling Engine is analyzing column types, computing statistics, assessing data quality, and detecting ML targets. This may take up to a few seconds depending on the file size.
              </CardDescription>
            </div>
            {/* Simple simulated progress steps */}
            <div className="flex justify-center gap-6 text-xs font-medium text-muted-foreground pt-4 max-w-lg mx-auto">
              <span className="flex items-center gap-1.5 text-primary"><Sparkles className="h-3.5 w-3.5 animate-pulse" /> Scanning CSV</span>
              <span className="flex items-center gap-1.5"><Sparkles className="h-3.5 w-3.5 opacity-50" /> Computing Statistics</span>
              <span className="flex items-center gap-1.5"><Sparkles className="h-3.5 w-3.5 opacity-50" /> Quality Audit</span>
            </div>
          </CardHeader>
        </Card>
      )}

      {/* 2. Profiling Failed State */}
      {dataset?.status === 'failed' && !isProfiling && (
        <Card className="border-destructive/30 bg-destructive/5 max-w-2xl mx-auto my-8">
          <CardContent className="flex flex-col items-center justify-center p-12 text-center">
            <AlertTriangle className="h-12 w-12 text-destructive mb-4" />
            <h3 className="text-xl font-bold text-destructive">Profiling Failed</h3>
            <p className="text-sm font-semibold text-muted-foreground mt-2">
              We couldn't analyze this dataset.
            </p>

            {dataset.error_message && (
              <p className="text-sm bg-destructive/10 border border-destructive/20 text-destructive px-4 py-2 rounded-md my-4 font-mono">
                Error: {dataset.error_message}
              </p>
            )}

            <div className="text-left max-w-md w-full bg-background border rounded-lg p-5 my-4 space-y-2">
              <span className="text-sm font-semibold text-foreground">Possible reasons:</span>
              <ul className="text-sm text-muted-foreground list-disc list-inside space-y-1 pl-1">
                <li>Unsupported or corrupted file</li>
                <li>Invalid dataset structure</li>
                <li>Parsing error</li>
              </ul>
            </div>

            <p className="text-sm text-muted-foreground">
              Please upload a valid CSV or Excel file and try again.
            </p>

            <Button onClick={handleAnalyze} className="mt-6 gap-2">
              <RefreshCw className="h-4 w-4" /> Try Again
            </Button>
          </CardContent>
        </Card>
      )}

      {/* 3. Initial state - Ask User to Analyze (Empty State UI) */}
      {!profile && !isProfiling && dataset?.status !== 'failed' && (
        <Card className="border-dashed max-w-2xl mx-auto my-8">
          <CardContent className="flex flex-col items-center justify-center p-12 text-center">
            <div className="rounded-full bg-primary/10 p-4 mb-4">
              <Database className="h-10 w-10 text-primary" />
            </div>
            <h3 className="text-2xl font-bold tracking-tight mb-2">Dataset Not Yet Analyzed</h3>
            <p className="text-sm text-muted-foreground max-w-md mb-8">
              Your dataset has been uploaded successfully, but it hasn't been analyzed yet.
              Run dataset profiling to generate quality metrics, statistics, preprocessing insights, and machine learning recommendations.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-left max-w-md w-full mb-8">
              {[
                "Dataset Statistics",
                "Missing Value Detection",
                "Duplicate Detection",
                "Column Analysis",
                "Machine Learning Recommendations"
              ].map((highlight) => (
                <div key={highlight} className="flex items-center gap-2">
                  <CheckCircle2 className="h-5 w-5 text-emerald-500 flex-shrink-0" />
                  <span className="text-sm font-medium">{highlight}</span>
                </div>
              ))}
            </div>

            <Button onClick={handleAnalyze} className="gap-2 size-lg px-8 py-6 text-base">
              <Sparkles className="h-5 w-5" /> Analyze Dataset
            </Button>
          </CardContent>
        </Card>
      )}

      {/* 4. Complete Profile Details Dashboard */}
      {profile && dataset?.status === 'completed' && !isProfiling && (
        <div className="space-y-6">
          {/* Quick Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7 gap-4">
            <Card className="shadow-sm">
              <CardHeader className="p-4 pb-1">
                <CardDescription className="text-xs font-semibold uppercase tracking-wider">Total Rows</CardDescription>
              </CardHeader>
              <CardContent className="p-4 pt-0">
                <div className="text-2xl font-bold">{profile.row_count.toLocaleString()}</div>
              </CardContent>
            </Card>

            <Card className="shadow-sm">
              <CardHeader className="p-4 pb-1">
                <CardDescription className="text-xs font-semibold uppercase tracking-wider">Total Columns</CardDescription>
              </CardHeader>
              <CardContent className="p-4 pt-0">
                <div className="text-2xl font-bold">{profile.column_count}</div>
              </CardContent>
            </Card>

            <Card className="shadow-sm">
              <CardHeader className="p-4 pb-1">
                <CardDescription className="text-xs font-semibold uppercase tracking-wider">Memory Size</CardDescription>
              </CardHeader>
              <CardContent className="p-4 pt-0">
                <div className="text-2xl font-bold">{formatBytes(profile.profile_data.general.memory_usage)}</div>
              </CardContent>
            </Card>

            <Card className="shadow-sm">
              <CardHeader className="p-4 pb-1">
                <CardDescription className="text-xs font-semibold uppercase tracking-wider">Missing Cells</CardDescription>
              </CardHeader>
              <CardContent className="p-4 pt-0">
                <div className="text-2xl font-bold flex items-baseline gap-1">
                  <span>{profile.profile_data.missing_values.total_missing_percentage.toFixed(1)}%</span>
                  <span className="text-xs text-muted-foreground">({profile.profile_data.missing_values.total_missing_count})</span>
                </div>
              </CardContent>
            </Card>

            <Card className="shadow-sm">
              <CardHeader className="p-4 pb-1">
                <CardDescription className="text-xs font-semibold uppercase tracking-wider">Duplicate Rows</CardDescription>
              </CardHeader>
              <CardContent className="p-4 pt-0">
                <div className="text-2xl font-bold flex items-baseline gap-1">
                  <span>{profile.profile_data.duplicates.percentage.toFixed(1)}%</span>
                  <span className="text-xs text-muted-foreground">({profile.profile_data.duplicates.count})</span>
                </div>
              </CardContent>
            </Card>

            <Card className="shadow-sm">
              <CardHeader className="p-4 pb-1">
                <CardDescription className="text-xs font-semibold uppercase tracking-wider">Quality Score</CardDescription>
              </CardHeader>
              <CardContent className="p-4 pt-0">
                <div className="text-2xl font-bold flex items-center gap-1.5">
                  <span>{profile.quality_score.toFixed(0)}%</span>
                  <Badge variant="outline" className={`${getQualityBadgeColor(profile.quality_level)} text-[10px] px-1 py-0 border-0.5`}>
                    {profile.quality_level}
                  </Badge>
                </div>
              </CardContent>
            </Card>

            <Card className="shadow-sm">
              <CardHeader className="p-4 pb-1">
                <CardDescription className="text-xs font-semibold uppercase tracking-wider">ML Task</CardDescription>
              </CardHeader>
              <CardContent className="p-4 pt-0">
                <div className="text-md font-bold truncate text-primary pt-0.5" title={profile.recommended_task}>
                  {profile.recommended_task}
                </div>
                {profile.recommended_target && (
                  <div className="text-[10px] text-muted-foreground truncate" title={`Target: ${profile.recommended_target}`}>
                    Target: <span className="font-semibold">{profile.recommended_target}</span>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Sub Navigation Tabs */}
          <div className="flex border-b gap-4">
            <button
              onClick={() => setActiveTab('overview')}
              className={`pb-2.5 text-sm font-medium border-b-2 px-1 transition-all ${
                activeTab === 'overview' ? 'border-primary text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
            >
              Overview
            </button>
            <button
              onClick={() => setActiveTab('columns')}
              className={`pb-2.5 text-sm font-medium border-b-2 px-1 transition-all ${
                activeTab === 'columns' ? 'border-primary text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
            >
              Column Schema & Stats
            </button>
            <button
              onClick={() => setActiveTab('preview')}
              className={`pb-2.5 text-sm font-medium border-b-2 px-1 transition-all ${
                activeTab === 'preview' ? 'border-primary text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
            >
              Data Preview
            </button>
            <button
              onClick={() => setActiveTab('recommendations')}
              className={`pb-2.5 text-sm font-medium border-b-2 px-1 transition-all ${
                activeTab === 'recommendations' ? 'border-primary text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
            >
              ML Recommendations
            </button>
          </div>

          {/* Tab Content Panel */}
          <div className="space-y-6">
            
            {/* OVERVIEW TAB */}
            {activeTab === 'overview' && (
              <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
                
                {/* Column Types Distribution */}
                <Card className="xl:col-span-2 shadow-sm">
                  <CardHeader>
                    <CardTitle className="text-lg">Column Type Distribution</CardTitle>
                    <CardDescription>Visual breakdown of column categories in this dataset.</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-6">
                    {/* Visual Segmented Bar */}
                    <div className="h-6 w-full rounded-md overflow-hidden bg-muted flex">
                      {Object.entries(profile.profile_data.general.column_types).map(([type, cols]) => {
                        const count = cols.length;
                        const pct = profile.column_count > 0 ? (count / profile.column_count) * 100 : 0;
                        if (count === 0) return null;
                        
                        let colorClass = 'bg-blue-500';
                        if (type === 'categorical') colorClass = 'bg-indigo-500';
                        if (type === 'boolean') colorClass = 'bg-emerald-500';
                        if (type === 'datetime') colorClass = 'bg-amber-500';
                        
                        return (
                          <div
                            key={type}
                            style={{ width: `${pct}%` }}
                            className={`${colorClass} h-full transition-all`}
                            title={`${type}: ${count} column(s) (${pct.toFixed(0)}%)`}
                          />
                        );
                      })}
                    </div>
                    
                    {/* Legend grid */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      {Object.entries(profile.profile_data.general.column_types).map(([type, cols]) => {
                        const count = cols.length;
                        let typeColor = 'bg-blue-500';
                        if (type === 'categorical') typeColor = 'bg-indigo-500';
                        if (type === 'boolean') typeColor = 'bg-emerald-500';
                        if (type === 'datetime') typeColor = 'bg-amber-500';

                        return (
                          <div key={type} className="flex items-center space-x-2 border rounded-lg p-3">
                            <span className={`h-3.5 w-3.5 rounded-full ${typeColor} shrink-0`} />
                            <div>
                              <div className="text-xs font-semibold capitalize">{type}</div>
                              <div className="text-sm font-bold mt-0.5">{count} cols</div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </CardContent>
                </Card>

                {/* Dataset Health Audit */}
                <Card className="xl:col-span-1 shadow-sm">
                  <CardHeader>
                    <CardTitle className="text-lg">Dataset Health Audit</CardTitle>
                    <CardDescription>Standard audit checks for ML preparation.</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {/* Missing cells check */}
                    <div className="flex items-start justify-between border-b pb-3 gap-2">
                      <div className="space-y-0.5">
                        <div className="text-sm font-semibold">Missing Values Audit</div>
                        <p className="text-xs text-muted-foreground">
                          Checks total null records.
                        </p>
                      </div>
                      {profile.profile_data.missing_values.total_missing_percentage > 10 ? (
                        <Badge variant="outline" className="bg-amber-500/10 text-amber-500 border-amber-500/20 text-xs gap-1 py-0.5 shrink-0">
                          <AlertTriangle className="h-3 w-3" /> High Warning
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="bg-emerald-500/10 text-emerald-500 border-emerald-500/20 text-xs gap-1 py-0.5 shrink-0">
                          <CheckCircle2 className="h-3 w-3" /> Healthy
                        </Badge>
                      )}
                    </div>

                    {/* Duplicates check */}
                    <div className="flex items-start justify-between border-b pb-3 gap-2">
                      <div className="space-y-0.5">
                        <div className="text-sm font-semibold">Duplicate Rows Audit</div>
                        <p className="text-xs text-muted-foreground">
                          Checks for duplicate rows.
                        </p>
                      </div>
                      {profile.profile_data.duplicates.percentage > 5 ? (
                        <Badge variant="outline" className="bg-amber-500/10 text-amber-500 border-amber-500/20 text-xs gap-1 py-0.5 shrink-0">
                          <AlertTriangle className="h-3 w-3" /> Warning
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="bg-emerald-500/10 text-emerald-500 border-emerald-500/20 text-xs gap-1 py-0.5 shrink-0">
                          <CheckCircle2 className="h-3 w-3" /> Healthy
                        </Badge>
                      )}
                    </div>

                    {/* Constant column check */}
                    <div className="flex items-start justify-between border-b pb-3 gap-2">
                      <div className="space-y-0.5">
                        <div className="text-sm font-semibold">Constant Columns</div>
                        <p className="text-xs text-muted-foreground">
                          Columns containing only one unique value.
                        </p>
                      </div>
                      {profile.profile_data.quality.penalties.columns.constant.count > 0 ? (
                        <Badge variant="outline" className="bg-amber-500/10 text-amber-500 border-amber-500/20 text-xs gap-1 py-0.5 shrink-0">
                          <AlertTriangle className="h-3 w-3" /> {profile.profile_data.quality.penalties.columns.constant.count} Flags
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="bg-emerald-500/10 text-emerald-500 border-emerald-500/20 text-xs gap-1 py-0.5 shrink-0">
                          <CheckCircle2 className="h-3 w-3" /> Healthy
                        </Badge>
                      )}
                    </div>

                    {/* High cardinality check */}
                    <div className="flex items-start justify-between pb-1 gap-2">
                      <div className="space-y-0.5">
                        <div className="text-sm font-semibold">High Cardinality</div>
                        <p className="text-xs text-muted-foreground">
                          Categorical columns acting as unique row keys.
                        </p>
                      </div>
                      {profile.profile_data.quality.penalties.columns.high_cardinality.count > 0 ? (
                        <Badge variant="outline" className="bg-amber-500/10 text-amber-500 border-amber-500/20 text-xs gap-1 py-0.5 shrink-0">
                          <AlertTriangle className="h-3 w-3" /> {profile.profile_data.quality.penalties.columns.high_cardinality.count} Flags
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="bg-emerald-500/10 text-emerald-500 border-emerald-500/20 text-xs gap-1 py-0.5 shrink-0">
                          <CheckCircle2 className="h-3 w-3" /> Healthy
                        </Badge>
                      )}
                    </div>
                  </CardContent>
                </Card>
              </div>
            )}

            {/* COLUMNS TAB */}
            {activeTab === 'columns' && (
              <Card className="shadow-sm">
                <CardHeader className="flex flex-col md:flex-row md:items-center justify-between pb-4 gap-4">
                  <div>
                    <CardTitle className="text-lg">Column Details & Statistics</CardTitle>
                    <CardDescription>Click any column to view comprehensive descriptive statistics.</CardDescription>
                  </div>
                  <div className="relative w-full md:w-80 shrink-0">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <input
                      type="text"
                      placeholder="Search columns..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="pl-9 h-9 w-full rounded-md border bg-background text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                    />
                  </div>
                </CardHeader>
                <CardContent className="p-0">
                  <div className="border-t">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="w-[30px]"></TableHead>
                          <TableHead>Column Name</TableHead>
                          <TableHead>Type</TableHead>
                          <TableHead>Cardinality</TableHead>
                          <TableHead>Missing</TableHead>
                          <TableHead className="text-right">Action</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {Object.values(profile.profile_data.columns)
                          .filter((col) => col.name.toLowerCase().includes(searchQuery.toLowerCase()))
                          .map((col) => {
                            const isExpanded = expandedColumn === col.name;
                            const isNumeric = col.type === 'numeric';
                            const isCategorical = col.type === 'categorical' || col.type === 'boolean';

                            return (
                              <Fragment key={col.name}>
                                <TableRow
                                  key={col.name}
                                  className="cursor-pointer hover:bg-muted/10 transition-colors"
                                  onClick={() => setExpandedColumn(isExpanded ? null : col.name)}
                                >
                                  <TableCell className="p-3 text-center">
                                    {isExpanded ? <ChevronUp className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
                                  </TableCell>
                                  <TableCell className="font-semibold">{col.name}</TableCell>
                                  <TableCell>
                                    <Badge variant="outline" className="gap-1.5 text-xs py-0.5 capitalize border-0 bg-accent hover:bg-accent">
                                      {getTypeIcon(col.type)}
                                      {col.type}
                                    </Badge>
                                  </TableCell>
                                  <TableCell>{col.cardinality.toLocaleString()}</TableCell>
                                  <TableCell>
                                    <div className="flex items-center space-x-2">
                                      <div className="w-16 bg-muted h-2 rounded-full overflow-hidden shrink-0">
                                        <div
                                          style={{ width: `${col.missing_percentage}%` }}
                                          className={`h-full ${col.missing_percentage > 10 ? 'bg-amber-500' : 'bg-primary'}`}
                                        />
                                      </div>
                                      <span className="text-xs text-muted-foreground">
                                        {col.missing_percentage.toFixed(1)}% ({col.missing_count})
                                      </span>
                                    </div>
                                  </TableCell>
                                  <TableCell className="text-right">
                                    <Button variant="ghost" size="sm" className="h-7 text-xs">
                                      {isExpanded ? 'Hide Stats' : 'Show Stats'}
                                    </Button>
                                  </TableCell>
                                </TableRow>
                                
                                {/* Expanded Statistics Block */}
                                {isExpanded && (
                                  <TableRow key={`${col.name}-stats`} className="bg-muted/5 hover:bg-muted/5">
                                    <TableCell colSpan={6} className="p-4 border-l-2 border-primary">
                                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                                        <div>
                                          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">General Metadata</h4>
                                          <div className="space-y-2 text-sm">
                                            <div className="flex justify-between border-b pb-1.5">
                                              <span>Null Rows</span>
                                              <span className="font-bold">{col.missing_count}</span>
                                            </div>
                                            <div className="flex justify-between border-b pb-1.5">
                                              <span>NonNull Rows</span>
                                              <span className="font-bold">{(profile.row_count - col.missing_count).toLocaleString()}</span>
                                            </div>
                                            <div className="flex justify-between border-b pb-1.5">
                                              <span>Unique Cardinality</span>
                                              <span className="font-bold">{col.cardinality.toLocaleString()}</span>
                                            </div>
                                          </div>
                                        </div>

                                        {/* Numeric stats */}
                                        {isNumeric && col.statistics && (
                                          <>
                                            <div>
                                              <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">Descriptive Stats</h4>
                                              <div className="space-y-2 text-sm">
                                                <div className="flex justify-between border-b pb-1.5">
                                                  <span>Mean</span>
                                                  <span className="font-bold">{col.statistics.mean?.toFixed(4) ?? 'N/A'}</span>
                                                </div>
                                                <div className="flex justify-between border-b pb-1.5">
                                                  <span>Std Dev</span>
                                                  <span className="font-bold">{col.statistics.std?.toFixed(4) ?? 'N/A'}</span>
                                                </div>
                                                <div className="flex justify-between border-b pb-1.5">
                                                  <span>Variance</span>
                                                  <span className="font-bold">{col.statistics.var?.toFixed(4) ?? 'N/A'}</span>
                                                </div>
                                                <div className="flex justify-between border-b pb-1.5">
                                                  <span>Mode</span>
                                                  <span className="font-bold">{col.statistics.mode ?? 'N/A'}</span>
                                                </div>
                                              </div>
                                            </div>

                                            <div>
                                              <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">Percentile Distribution</h4>
                                              <div className="space-y-2 text-sm">
                                                <div className="flex justify-between border-b pb-1.5">
                                                  <span>Minimum</span>
                                                  <span className="font-bold">{col.statistics.min ?? 'N/A'}</span>
                                                </div>
                                                <div className="flex justify-between border-b pb-1.5">
                                                  <span>Q1 (25%)</span>
                                                  <span className="font-bold">{col.statistics.q1 ?? 'N/A'}</span>
                                                </div>
                                                <div className="flex justify-between border-b pb-1.5">
                                                  <span>Median (50%)</span>
                                                  <span className="font-bold">{col.statistics.median ?? 'N/A'}</span>
                                                </div>
                                                <div className="flex justify-between border-b pb-1.5">
                                                  <span>Q3 (75%)</span>
                                                  <span className="font-bold">{col.statistics.q3 ?? 'N/A'}</span>
                                                </div>
                                                <div className="flex justify-between border-b pb-1.5">
                                                  <span>Maximum</span>
                                                  <span className="font-bold">{col.statistics.max ?? 'N/A'}</span>
                                                </div>
                                              </div>
                                            </div>
                                          </>
                                        )}

                                        {/* Categorical stats */}
                                        {isCategorical && col.statistics && (
                                          <div className="md:col-span-2">
                                            <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">Unique / Most Frequent Metrics</h4>
                                            <div className="space-y-3 text-sm">
                                              <div className="flex justify-between border-b pb-1.5">
                                                <span>Most Frequent Value</span>
                                                <span className="font-bold text-primary">{col.statistics.most_frequent ?? 'N/A'}</span>
                                              </div>
                                              <div>
                                                <span className="text-xs text-muted-foreground block mb-2 font-medium">Sample Unique Values (Up to 20)</span>
                                                <div className="flex flex-wrap gap-1.5 max-h-24 overflow-y-auto border p-2 rounded-lg bg-card">
                                                  {col.statistics.unique_values && col.statistics.unique_values.length > 0 ? (
                                                    col.statistics.unique_values.map((v) => (
                                                      <Badge key={v} variant="outline" className="text-[10px] py-0.5 bg-muted/30">
                                                        {v === null || v === 'None' ? <span className="italic text-muted-foreground">null</span> : v}
                                                      </Badge>
                                                    ))
                                                  ) : (
                                                    <span className="text-xs text-muted-foreground">No sample values</span>
                                                  )}
                                                </div>
                                              </div>
                                            </div>
                                          </div>
                                        )}
                                      </div>
                                    </TableCell>
                                  </TableRow>
                                )}
                              </Fragment>
                            );
                          })}
                      </TableBody>
                    </Table>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* DATA PREVIEW TAB */}
            {activeTab === 'preview' && (
              <Card className="shadow-sm">
                <CardHeader>
                  <CardTitle className="text-lg">Dataset Preview</CardTitle>
                  <CardDescription>Viewing the first 10 rows (head(10)) of the uploaded dataset file.</CardDescription>
                </CardHeader>
                <CardContent className="p-0 border-t overflow-hidden">
                  {profile.profile_data.preview && profile.profile_data.preview.length > 0 ? (
                    <div className="overflow-x-auto w-full max-h-[450px]">
                      <Table>
                        <TableHeader className="bg-muted/40 sticky top-0 z-10">
                          <TableRow>
                            {Object.keys(profile.profile_data.preview[0]).map((header) => (
                              <TableHead key={header} className="font-bold whitespace-nowrap">
                                {header}
                              </TableHead>
                            ))}
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {profile.profile_data.preview.map((row, idx) => (
                            <TableRow key={idx} className="hover:bg-muted/10">
                              {Object.values(row).map((val, cellIdx) => (
                                <TableCell key={cellIdx} className="whitespace-nowrap max-w-[200px] truncate">
                                  {val === null || val === 'None' ? (
                                    <span className="italic text-muted-foreground text-xs bg-muted/40 px-1.5 py-0.5 rounded">null</span>
                                  ) : (
                                    String(val)
                                  )}
                                </TableCell>
                              ))}
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  ) : (
                    <div className="flex flex-col items-center justify-center p-12 text-center text-muted-foreground">
                      <Eye className="h-10 w-10 mb-2 opacity-50" />
                      <span>No preview data available</span>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}

            {/* ML RECOMMENDATIONS TAB */}
            {activeTab === 'recommendations' && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                
                {/* Recommendation details */}
                <Card className="shadow-sm">
                  <CardHeader>
                    <CardTitle className="text-lg flex items-center gap-2">
                      <Sparkles className="h-5 w-5 text-primary" />
                      Suggested ML Architecture
                    </CardTitle>
                    <CardDescription>
                      Heuristics used by AutoDS AI to establish training templates.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-6">
                    <div className="flex items-center justify-between border-b pb-4">
                      <span className="text-sm font-medium text-muted-foreground">Recommended ML Task</span>
                      <Badge className="text-sm font-bold bg-primary text-primary-foreground">
                        {profile.recommended_task}
                      </Badge>
                    </div>

                    <div className="flex items-center justify-between border-b pb-4">
                      <span className="text-sm font-medium text-muted-foreground">Detected Target Column</span>
                      <span className="font-bold text-primary text-sm font-mono">
                        {profile.recommended_target ? profile.recommended_target : 'None (Unsupervised)'}
                      </span>
                    </div>

                    <div className="flex items-center justify-between border-b pb-4">
                      <span className="text-sm font-medium text-muted-foreground">Confidence Score</span>
                      <div className="flex items-center space-x-2">
                        <div className="w-24 bg-muted h-2.5 rounded-full overflow-hidden shrink-0">
                          <div
                            style={{ width: `${profile.profile_data.ml_recommendation.confidence}%` }}
                            className="h-full bg-primary"
                          />
                        </div>
                        <span className="font-bold text-sm">
                          {profile.profile_data.ml_recommendation.confidence.toFixed(0)}%
                        </span>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Explanation heuristic logs */}
                <Card className="shadow-sm">
                  <CardHeader>
                    <CardTitle className="text-lg">Target & Task Inference Reasons</CardTitle>
                    <CardDescription>How the target column and task were identified.</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="bg-muted/30 border p-4 rounded-lg space-y-3">
                      {profile.profile_data.ml_recommendation.explanation.reasons.map((reason, idx) => (
                        <div key={idx} className="flex items-start space-x-2.5 text-sm">
                          <CheckCircle2 className="h-4.5 w-4.5 text-primary shrink-0 mt-0.5" />
                          <span className="text-muted-foreground">{reason}</span>
                        </div>
                      ))}
                    </div>

                    <p className="text-xs text-muted-foreground leading-relaxed">
                      💡 <strong>Note:</strong> Target detection assigns points to columns located at the end of the file or containing matching terms (like <em>price, label, churn</em>) while penalizing ID keywords and high-cardinality row indicators. The suggested task is selected by analysing whether the target is discrete (Classification) or continuous (Regression).
                    </p>
                  </CardContent>
                </Card>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
