const SIZE = 18;
const STROKE = 2;
const R = (SIZE - STROKE) / 2;
const CIRCUMFERENCE = 2 * Math.PI * R;
const GAP = CIRCUMFERENCE * 0.2;
const LINE_H = 24;

function PendingIcon() {
    return (
        <svg width={SIZE} height={SIZE} className="flex-shrink-0">
            <circle
                cx={SIZE / 2} cy={SIZE / 2} r={R}
                fill="none" stroke="#d1d5db" strokeWidth={STROKE}
            />
        </svg>
    );
}

function SpinnerIcon() {
    return (
        <svg width={SIZE} height={SIZE} className="flex-shrink-0 animate-spin">
            <circle
                cx={SIZE / 2} cy={SIZE / 2} r={R}
                fill="none"
                stroke="#16a34a"
                strokeWidth={STROKE}
                strokeDasharray={`${CIRCUMFERENCE - GAP} ${GAP}`}
                strokeLinecap="round"
            />
        </svg>
    );
}

function CompletedIcon() {
    return (
        <svg width={SIZE} height={SIZE} className="flex-shrink-0 animate-scale-check">
            <circle cx={SIZE / 2} cy={SIZE / 2} r={R} fill="#16a34a" />
            <path
                d="M6 9.5L8.5 12L12.5 7"
                fill="none" stroke="white" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round"
            />
        </svg>
    );
}

function FailedIcon() {
    return (
        <svg width={SIZE} height={SIZE} className="flex-shrink-0">
            <circle cx={SIZE / 2} cy={SIZE / 2} r={R} fill="#ef4444" />
            <path
                d="M6.5 6.5L11.5 11.5M11.5 6.5L6.5 11.5"
                fill="none" stroke="white" strokeWidth={1.8} strokeLinecap="round"
            />
        </svg>
    );
}

const iconMap = {
    pending: PendingIcon,
    processing: SpinnerIcon,
    completed: CompletedIcon,
    failed: FailedIcon,
};

const textClassMap = {
    pending: 'text-text-muted',
    processing: 'text-text-primary font-medium',
    completed: 'text-text-primary',
    failed: 'text-red-500',
};

export default function AgentTaskList({ steps }) {
    return (
        <div className="flex justify-start mb-4 w-full">
            <div className="rounded-xl px-4 py-3 max-w-md">
                {steps.map((step, index) => {
                    const Icon = iconMap[step.status] || iconMap.pending;
                    const textClass = textClassMap[step.status] || textClassMap.pending;
                    const isLast = index === steps.length - 1;
                    const lineFilled = step.status === 'completed' || step.status === 'failed';

                    return (
                        <div
                            key={step.id}
                            className={`flex animate-slide-up ${step.isSubstep ? 'ml-6' : ''}`}
                            style={{
                                animationDelay: `${index * 80}ms`,
                                animationFillMode: 'both',
                            }}
                        >
                            <div className="flex flex-col items-center" style={{ width: SIZE }}>
                                <Icon />
                                {!isLast && (
                                    <div
                                        className="relative rounded-full overflow-hidden"
                                        style={{
                                            width: 2,
                                            height: LINE_H,
                                            backgroundColor: '#e5e7eb',
                                        }}
                                    >
                                        <div
                                            className="absolute inset-x-0 top-0 rounded-full"
                                            style={{
                                                width: '100%',
                                                height: lineFilled ? '100%' : '0%',
                                                backgroundColor: '#16a34a',
                                                transition: 'height 0.5s ease-out',
                                            }}
                                        />
                                    </div>
                                )}
                            </div>
                            <span className={`text-sm ml-3 leading-[${SIZE}px] ${textClass}`}
                                style={{ lineHeight: `${SIZE}px` }}
                            >
                                {step.label}
                            </span>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
