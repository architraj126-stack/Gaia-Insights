import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, ArrowRight, Construction, Info } from 'lucide-react';
import { StatusChip } from './StatusChip';
import { StepIndicator } from './StepIndicator';

export interface PagePlaceholderProps {
  step: number;
  title: string;
  subtitle: string;
  plannedPhase: string;
  description: string;
  prevPath?: string;
  nextPath?: string;
  prevLabel?: string;
  nextLabel?: string;
  children?: React.ReactNode;
}

export const PagePlaceholder: React.FC<PagePlaceholderProps> = ({
  step,
  title,
  subtitle,
  plannedPhase,
  description,
  prevPath,
  nextPath,
  prevLabel = 'Previous Step',
  nextLabel = 'Next Step',
  children,
}) => {
  return (
    <div className="flex flex-col min-h-[calc(100vh-4rem)]">
      {/* 5-step indicator on analysis pages */}
      <StepIndicator currentStep={step} />

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border-subtle pb-6">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-mono font-semibold text-cyan-400 uppercase tracking-wider">
                Step {step} of 5
              </span>
              <span className="text-slate-600">•</span>
              <StatusChip status="Unavailable" customLabel="Not built yet" />
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">{title}</h1>
            <p className="text-sm text-slate-400 mt-1 italic font-medium">{subtitle}</p>
          </div>

          <div className="flex items-center gap-3">
            {prevPath && (
              <Link
                to={prevPath}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-navy-800 border border-slate-700 text-xs font-medium text-slate-300 hover:bg-navy-700 hover:text-white transition-colors"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                <span>{prevLabel}</span>
              </Link>
            )}

            {nextPath && (
              <Link
                to={nextPath}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-accent-blue/20 border border-accent-blue/40 text-xs font-medium text-cyan-300 hover:bg-accent-blue/30 transition-colors"
              >
                <span>{nextLabel}</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            )}
          </div>
        </div>

        {/* Optional Custom Injected Content (e.g. Session State from Page 1) */}
        {children}

        {/* Not Built Yet Placeholder Card */}
        <div className="bg-navy-850 border border-border-subtle rounded-card p-8 sm:p-12 text-center space-y-6 max-w-3xl mx-auto my-8">
          <div className="w-16 h-16 rounded-2xl bg-navy-800 border border-slate-700/80 mx-auto flex items-center justify-center text-accent-cyan shadow-lg shadow-black/40">
            <Construction className="w-8 h-8" />
          </div>

          <div className="space-y-2">
            <h2 className="text-xl font-bold text-slate-100">Not built yet</h2>
            <p className="text-sm text-slate-400 max-w-lg mx-auto leading-relaxed">
              {description}
            </p>
          </div>

          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-md bg-navy-900 border border-border-subtle text-xs font-mono text-slate-300">
            <Info className="w-3.5 h-3.5 text-accent-blue shrink-0" />
            <span>Target Implementation: {plannedPhase} (No placeholder numbers displayed)</span>
          </div>
        </div>
      </main>
    </div>
  );
};
