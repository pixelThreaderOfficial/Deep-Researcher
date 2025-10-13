import React from 'react';
import { motion } from 'framer-motion';
import {
    Flag,
    FileCog,
    HelpCircle
} from 'lucide-react';
import {
    Tooltip,
    TooltipContent,
    TooltipTrigger,
} from "@/components/ui/tooltip"

const CTAComponent = () => {
    const ctaActions = [
        {
            id: 'report',
            name: 'Report',
            icon: Flag,
            action: () => {
                // Open report modal or navigate to report page
                console.log('Opening report modal...');
                // You can implement actual report functionality here
            }
        },
        {
            id: 'system-prompt',
            name: 'System Prompt',
            icon: FileCog,
            action: () => {
                // Open system prompt settings
                console.log('Opening system prompt settings...');
                // You can implement modal or navigation to settings here
            }
        },
        {
            id: 'docs-help',
            name: 'Docs/Help',
            icon: HelpCircle,
            action: () => {
                // Open documentation or help
                console.log('Opening documentation/help...');
                // You can implement help modal or navigation to docs here
            }
        }
    ];

    const handleAction = (action) => {
        action();
    };

    return (
        <div className="fixed bottom-6 right-6 z-50">
            <div className="flex flex-col items-end space-y-3">
                {ctaActions.map((action, index) => (
                    <Tooltip key={action.id}>
                        <TooltipTrigger asChild>
                            <motion.div
                                initial={{ opacity: 0, scale: 0, y: 20 }}
                                animate={{
                                    opacity: 1,
                                    scale: 1,
                                    y: 0,
                                    transition: {
                                        delay: index * 0.1,
                                        duration: 0.4,
                                        ease: "easeInOut"
                                    }
                                }}
                                whileHover={{
                                    scale: 1.1,
                                    boxShadow: "0 10px 25px rgba(0,0,0,0.3)"
                                }}
                                whileTap={{ scale: 0.95 }}
                                className="w-12 h-12 bg-gray-800/70 hover:bg-gray-700/80 border border-gray-700/50 hover:border-gray-600/50 rounded-full flex items-center justify-center shadow-lg cursor-pointer transition-all duration-200 backdrop-blur-sm"
                                onClick={() => handleAction(action.action)}
                            >
                                <action.icon className="w-5 h-5 text-gray-200 hover:text-white" />
                            </motion.div>
                        </TooltipTrigger>
                        <TooltipContent
                            side="left"
                            hideArrow={true}
                            className="bg-gray-800 border border-gray-700 text-white text-sm px-3 py-1 rounded-lg shadow-lg me-2"
                        >
                            {action.name}
                        </TooltipContent>
                    </Tooltip>
                ))}
            </div>
        </div>
    );
};

export default CTAComponent;
