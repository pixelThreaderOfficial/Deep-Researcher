import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { ChevronDown } from 'lucide-react';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from './dropdown-menu';

const StyledDropdown = ({
    value,
    onValueChange,
    options = [],
    placeholder = "Select option",
    className = "",
    width = "w-full"
}) => {
    const [isOpen, setIsOpen] = useState(false);

    const selectedOption = options.find(option => option.value === value);

    const handleSelect = (optionValue) => {
        onValueChange(optionValue);
    };

    return (
        <div className={width}>
            <DropdownMenu onOpenChange={setIsOpen}>
                <DropdownMenuTrigger asChild>
                    <button
                        className={`flex items-center gap-2 text-gray-300 hover:text-gray-100 hover:bg-gray-600 transition-all duration-200 border rounded-lg px-3 py-2 cursor-pointer focus:outline-none w-full justify-between min-h-[30px] ${isOpen
                            ? 'border-gray-700/40 bg-gray-700/20'
                            : 'border-gray-600/30'
                            } ${className}`}
                        onClick={(e) => e.stopPropagation()}
                    >
                        <span className="text-sm font-medium truncate">
                            {selectedOption ? selectedOption.name : placeholder}
                        </span>
                        <ChevronDown className="w-4 h-4 flex-shrink-0" />
                    </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent className="bg-gray-800 border border-gray-600 rounded-lg shadow-lg z-50 min-w-[200px]" sideOffset={8}>
                    {options.map((option) => (
                        <DropdownMenuItem
                            key={option.value}
                            onClick={() => handleSelect(option.value)}
                            className="text-gray-200 hover:bg-gray-700 focus:bg-gray-700 hover:text-gray-200 focus:text-gray-200 cursor-pointer px-3 py-2"
                        >
                            <div>
                                <div className="font-medium">{option.name}</div>
                                {option.description && (
                                    <div className="text-xs text-gray-400">{option.description}</div>
                                )}
                            </div>
                        </DropdownMenuItem>
                    ))}
                </DropdownMenuContent>
            </DropdownMenu>
        </div>
    );
};

export default StyledDropdown;