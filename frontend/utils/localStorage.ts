/**
 * Local Storage Service for Wallet and Address Management
 * Handles card type detection, encryption, and CRUD operations
 */

// ============================================
// CARD TYPE DETECTION
// ============================================

export function detectCardType(cardNumber: string): string {
    const number = cardNumber.replace(/\s|-/g, '');

    // Visa: starts with 4
    if (number[0] === '4') return 'visa';

    // Mastercard: starts with 51-55 or 2221-2720
    if (['51', '52', '53', '54', '55'].includes(number.slice(0, 2))) return 'mastercard';
    const firstFour = parseInt(number.slice(0, 4));
    if (firstFour >= 2221 && firstFour <= 2720) return 'mastercard';

    // Amex: starts with 34 or 37
    if (['34', '37'].includes(number.slice(0, 2))) return 'amex';

    // Discover: starts with 6011, 622126-622925, 644-649, 65
    if (number.slice(0, 4) === '6011' || number.slice(0, 2) === '65') return 'discover';
    const firstSix = parseInt(number.slice(0, 6));
    if (firstSix >= 622126 && firstSix <= 622925) return 'discover';
    if (['644', '645', '646', '647', '648', '649'].includes(number.slice(0, 3))) return 'discover';

    return 'unknown';
}

// ============================================
// ENCRYPTION (Simple Base64 - upgrade to Web Crypto API for production)
// ============================================

function encrypt(data: string): string {
    return btoa(data);
}

function decrypt(data: string): string {
    return atob(data);
}

// ============================================
// PAYMENT METHODS
// ============================================

export interface PaymentMethod {
    id: string;
    type: 'card' | 'upi';
    cardType?: string;
    label: string;
    maskedData: string;
    encryptedData: string;
    isDefault: boolean;
    createdAt: string;
}

export interface CardData {
    cardNumber: string;
    cardHolder: string;
    expiryMonth: string;
    expiryYear: string;
    cvv: string;
}

function maskCardNumber(cardNumber: string): string {
    const cleaned = cardNumber.replace(/\s|-/g, '');
    return `**** **** **** ${cleaned.slice(-4)}`;
}

export function savePaymentMethod(
    type: 'card' | 'upi',
    data: CardData | { upiId: string },
    label?: string,
    isDefault: boolean = false
): PaymentMethod {
    const methods = getPaymentMethods();

    // If setting as default, unset others
    if (isDefault) {
        methods.forEach(m => m.isDefault = false);
    }

    let maskedData: string;
    let cardType: string | undefined;

    if (type === 'card') {
        const cardData = data as CardData;
        cardType = detectCardType(cardData.cardNumber);
        maskedData = maskCardNumber(cardData.cardNumber);
    } else {
        maskedData = (data as { upiId: string }).upiId;
    }

    const newMethod: PaymentMethod = {
        id: crypto.randomUUID(),
        type,
        cardType,
        label: label || maskedData,
        maskedData,
        encryptedData: encrypt(JSON.stringify(data)),
        isDefault,
        createdAt: new Date().toISOString(),
    };

    methods.push(newMethod);
    localStorage.setItem('paymentMethods', JSON.stringify(methods));
    return newMethod;
}

export function getPaymentMethods(): PaymentMethod[] {
    const data = localStorage.getItem('paymentMethods');
    return data ? JSON.parse(data) : [];
}

export function getPaymentMethod(id: string, decrypted: boolean = false): PaymentMethod | null {
    const methods = getPaymentMethods();
    const method = methods.find(m => m.id === id);

    if (method && decrypted) {
        return {
            ...method,
            decryptedData: JSON.parse(decrypt(method.encryptedData)),
        } as any;
    }

    return method || null;
}

export function updatePaymentMethod(id: string, updates: Partial<PaymentMethod>): void {
    const methods = getPaymentMethods();
    const index = methods.findIndex(m => m.id === id);

    if (index !== -1) {
        if (updates.isDefault) {
            methods.forEach(m => m.isDefault = false);
        }
        methods[index] = { ...methods[index], ...updates };
        localStorage.setItem('paymentMethods', JSON.stringify(methods));
    }
}

export function deletePaymentMethod(id: string): void {
    const methods = getPaymentMethods().filter(m => m.id !== id);
    localStorage.setItem('paymentMethods', JSON.stringify(methods));
}

export function setDefaultPaymentMethod(id: string): void {
    const methods = getPaymentMethods();
    methods.forEach(m => m.isDefault = m.id === id);
    localStorage.setItem('paymentMethods', JSON.stringify(methods));
}

// ============================================
// ADDRESSES
// ============================================

export interface Address {
    id: string;
    type: 'shipping' | 'billing';
    fullName: string;
    addressLine1: string;
    addressLine2?: string;
    city: string;
    state: string;
    postalCode: string;
    country: string;
    phone?: string;
    isDefault: boolean;
    createdAt: string;
}

export function saveAddress(address: Omit<Address, 'id' | 'createdAt'>): Address {
    const addresses = getAddresses();

    if (address.isDefault) {
        addresses.forEach(a => a.isDefault = false);
    }

    const newAddress: Address = {
        ...address,
        id: crypto.randomUUID(),
        createdAt: new Date().toISOString(),
    };

    addresses.push(newAddress);
    localStorage.setItem('addresses', JSON.stringify(addresses));
    return newAddress;
}

export function getAddresses(): Address[] {
    const data = localStorage.getItem('addresses');
    return data ? JSON.parse(data) : [];
}

export function getAddress(id: string): Address | null {
    const addresses = getAddresses();
    return addresses.find(a => a.id === id) || null;
}

export function updateAddress(id: string, updates: Partial<Address>): void {
    const addresses = getAddresses();
    const index = addresses.findIndex(a => a.id === id);

    if (index !== -1) {
        if (updates.isDefault) {
            addresses.forEach(a => a.isDefault = false);
        }
        addresses[index] = { ...addresses[index], ...updates };
        localStorage.setItem('addresses', JSON.stringify(addresses));
    }
}

export function deleteAddress(id: string): void {
    const addresses = getAddresses().filter(a => a.id !== id);
    localStorage.setItem('addresses', JSON.stringify(addresses));
}

export function setDefaultAddress(id: string): void {
    const addresses = getAddresses();
    addresses.forEach(a => a.isDefault = a.id === id);
    localStorage.setItem('addresses', JSON.stringify(addresses));
}

// ============================================
// UTILITY FUNCTIONS
// ============================================

export function exportData(): string {
    return JSON.stringify({
        paymentMethods: getPaymentMethods(),
        addresses: getAddresses(),
    });
}

export function importData(jsonData: string): void {
    try {
        const data = JSON.parse(jsonData);
        if (data.paymentMethods) {
            localStorage.setItem('paymentMethods', JSON.stringify(data.paymentMethods));
        }
        if (data.addresses) {
            localStorage.setItem('addresses', JSON.stringify(data.addresses));
        }
    } catch (error) {
        console.error('Failed to import data:', error);
        throw new Error('Invalid data format');
    }
}

export function clearAllData(): void {
    localStorage.removeItem('paymentMethods');
    localStorage.removeItem('addresses');
}
