import React from 'react';
import { NavLink } from 'react-router-dom';
import { Check, ChevronRight } from 'lucide-react';

export interface StepItem {
  step: number;
  label: string;
  question: string;
  path: string;
}

export const ANALYSIS_STEPS: StepItem[] = [
  { step: 1, label: 'Data Explorer', question: 'What should I study?', path: '/explore' },
  { step: 2, label: 'Geographic Explorer', question: 'Where should I study?', path: '/region' },
  { step: 3, label: 'Trend Analysis', question: 'How did it change over time?', path: '/trends' },
  { step: 4, label: 'Change Detection', question: 'Where did it change?', path: '/changes' },
  { step: 5, label: 'Significance & Reports', question: 'How strong is the evidence?', path: '/significance' },
];

export interface StepIndicatorProps {
  currentStep: number;
}

export const StepIndicator: React.FC<StepIndicatorProps> = ({ currentStep }) => {
  return (
    <div className="w-full bg-navy-850 border-b border-border-subtle py-3 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto">
        <nav aria-label="Analysis Workflow Steps" className="overflow-x-auto scrollbar-none">
          <ol className="flex items-center min-w-[700px] justify-between">
            {ANALYSIS_STEPS.map((item, index) => {
              const isCurrent = item.step === currentStep;
              const isPassed = item.step < currentStep;

              return (
                <li key={item.step} className="flex items-center flex-1 last:flex-initial">
                  <NavLink
                    to={item.path}
                    className={`group flex items-center gap-3 p-1 rounded-md transition-all ${
                      isCurrent
                        ? 'opacity-100'
                        : isPassed
                        ? 'opacity-85 hover:opacity-100'
                        : 'opacity-50 hover:opacity-75'
                    }`}
                  >
                    {/* Step circle indicator */}
                    <div
                      className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-all shrink-0 ${
                        isCurrent
                          ? 'bg-gradient-to-tr from-accent-blue to-accent-cyan text-navy-950 ring-2 ring-accent-cyan/50 shadow-md shadow-accent-cyan/20'
                          : isPassed
                          ? 'bg-accent-blue/20 text-cyan-300 border border-accent-blue/50'
                          : 'bg-navy-800 text-slate-400 border border-slate-700'
                      }`}
                    >
                      {isPassed ? <Check className="w-3.5 h-3.5" /> : item.step}
                    </div>

                    {/* Step texts */}
                    <div className="flex flex-col text-left">
                      <span
                        className={`text-xs font-semibold tracking-tight transition-colors ${
                          isCurrent
                            ? 'text-cyan-300'
                            : isPassed
                            ? 'text-slate-200'
                            : 'text-slate-400'
                        }`}
                      >
                        {item.label}
                      </span>
                      <span className="text-[11px] text-slate-500 hidden sm:block">
                        {item.question}
                      </span>
                    </div>
                  </NavLink>

                  {/* Divider chevron */}
                  {index < ANALYSIS_STEPS.length - 1 && (
                    <div className="flex-1 flex justify-center px-2">
                      <ChevronRight className="w-4 h-4 text-slate-700 shrink-0" />
                    </div>
                  )}
                </li>
              );
            })}
          </ol>
        </nav>
      </div>
    </div>
  );
};
