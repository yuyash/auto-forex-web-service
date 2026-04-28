import { useState, useEffect, useMemo, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Box,
  Stepper,
  Step,
  StepLabel,
  Button,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Typography,
  Alert,
  CircularProgress,
  Divider,
  Card,
  CardContent,
} from '@mui/material';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import StrategyConfigForm from '../strategy/StrategyConfigForm';
import { useStrategies, useStrategyDefaults } from '../../hooks/useStrategies';
import type { StrategyConfigCreateData } from '../../types/configuration';
import type { StrategyConfig, ConfigSchema } from '../../types/strategy';
import { STRATEGY_CONFIG_SCHEMAS } from './strategyConfigSchemas';
import { isParameterVisible } from '../../utils/strategySchemaDependsOn';
import { orderConfigEntries } from '../../utils/configFieldOrder';

// Validation schema
const configurationSchema = z.object({
  name: z
    .string()
    .min(1, 'Name is required')
    .max(100, 'Name must be less than 100 characters'),
  strategy_type: z.string().min(1, 'Strategy type is required'),
  description: z
    .string()
    .max(500, 'Description must be less than 500 characters')
    .optional(),
  parameters: z.record(z.string(), z.unknown()),
});

type ConfigurationFormData = z.infer<typeof configurationSchema>;

interface ConfigurationFormProps {
  mode?: 'create' | 'edit';
  initialData?: Partial<ConfigurationFormData>;
  onSubmit: (data: StrategyConfigCreateData) => Promise<void>;
  onCancel: () => void;
  isLoading?: boolean;
}

const getDefaultParameters = (
  strategyType: string,
  schema?: ConfigSchema,
  apiDefaults?: StrategyConfig
): StrategyConfig => {
  const effectiveSchema = schema ?? STRATEGY_CONFIG_SCHEMAS[strategyType];

  if (effectiveSchema) {
    const defaults: StrategyConfig = {};

    Object.entries(effectiveSchema.properties).forEach(([key, property]) => {
      if (property.deferDefaultUntilConfigured) {
        return;
      }
      if (property.default !== undefined) {
        defaults[key] = property.default;
      }
    });

    const merged = apiDefaults ? { ...defaults, ...apiDefaults } : defaults;
    Object.entries(effectiveSchema.properties).forEach(([key, property]) => {
      if (!property.deferDefaultUntilConfigured) {
        return;
      }
      delete merged[key];
    });
    return merged;
  }

  return apiDefaults ? { ...apiDefaults } : {};
};

const ConfigurationForm = ({
  mode = 'create',
  initialData,
  onSubmit,
  onCancel,
  isLoading = false,
}: ConfigurationFormProps) => {
  const { t, i18n } = useTranslation(['configuration', 'common', 'strategy']);
  const {
    strategies,
    isLoading: isStrategiesLoading,
    error: strategiesError,
  } = useStrategies();

  const isEditMode = mode === 'edit';
  const initialStrategyType = initialData?.strategy_type || '';
  const initialStrategySchema = useMemo<ConfigSchema | undefined>(() => {
    if (!initialStrategyType) return undefined;

    // The backend JSON schema is the single source of truth.
    // STRATEGY_CONFIG_SCHEMAS is checked first as an optional override
    // but is normally empty.
    const frontendSchema = STRATEGY_CONFIG_SCHEMAS[initialStrategyType];
    if (frontendSchema) return frontendSchema;

    const fromApi = strategies.find((s) => s.id === initialStrategyType)
      ?.config_schema as unknown;

    if (
      fromApi &&
      typeof fromApi === 'object' &&
      fromApi !== null &&
      'properties' in fromApi
    ) {
      return fromApi as ConfigSchema;
    }

    return undefined;
  }, [initialStrategyType, strategies]);

  const initialParameters = useMemo<StrategyConfig>(() => {
    const defaults = initialStrategyType
      ? getDefaultParameters(initialStrategyType, initialStrategySchema)
      : {};

    if (initialData?.parameters) {
      return {
        ...defaults,
        ...initialData.parameters,
      };
    }

    return defaults;
  }, [initialStrategyType, initialData, initialStrategySchema]);

  const [activeStep, setActiveStep] = useState(0);
  const [parameters, setParameters] =
    useState<StrategyConfig>(initialParameters);

  const hasUserEditedParamsRef = useRef(false);
  const lastDefaultsStrategyRef = useRef<string>('');

  const {
    control,
    handleSubmit,
    watch,
    setValue,
    trigger,
    formState: { errors },
  } = useForm<ConfigurationFormData>({
    resolver: zodResolver(configurationSchema),
    defaultValues: {
      name: initialData?.name || '',
      strategy_type: initialStrategyType,
      description: initialData?.description || '',
      parameters: initialParameters,
    },
  });

  // Watch strategy_type for reactivity
  // eslint-disable-next-line react-hooks/incompatible-library
  const selectedStrategyType = watch('strategy_type');

  const selectedStrategy = useMemo(() => {
    return strategies.find((s) => s.id === selectedStrategyType);
  }, [strategies, selectedStrategyType]);
  const selectableStrategies = useMemo(() => {
    return strategies.filter(
      (strategy) => strategy.id !== 'custom' || initialStrategyType === 'custom'
    );
  }, [initialStrategyType, strategies]);
  const { data: strategyDefaults } = useStrategyDefaults(
    selectedStrategyType || undefined,
    { enabled: Boolean(selectedStrategyType) }
  );

  const strategySchema = useMemo<ConfigSchema | undefined>(() => {
    if (!selectedStrategyType) return undefined;

    // The backend JSON schema is the single source of truth.
    // STRATEGY_CONFIG_SCHEMAS is checked first as an optional override.
    const frontendSchema = STRATEGY_CONFIG_SCHEMAS[selectedStrategyType];
    if (frontendSchema) return frontendSchema;

    const fromApi = selectedStrategy?.config_schema as unknown;
    if (
      fromApi &&
      typeof fromApi === 'object' &&
      fromApi !== null &&
      'properties' in fromApi
    ) {
      return fromApi as ConfigSchema;
    }

    return undefined;
  }, [selectedStrategy, selectedStrategyType]);

  const previousStrategyTypeRef = useRef<string>(initialStrategyType || '');
  const previousInitialDataRef =
    useRef<ConfigurationFormProps['initialData']>(initialData);

  useEffect(() => {
    lastDefaultsStrategyRef.current = selectedStrategyType || '';
  }, [selectedStrategyType, strategyDefaults]);

  // Update parameters when strategy type or initial data changes
  useEffect(() => {
    const currentType = selectedStrategyType || '';
    const previousType = previousStrategyTypeRef.current;
    const initialDataChanged = previousInitialDataRef.current !== initialData;

    if (currentType && currentType !== previousType) {
      hasUserEditedParamsRef.current = false;
    }

    if (!currentType) {
      if (previousType) {
        setParameters({});
        setValue('parameters', {});
      }
      previousStrategyTypeRef.current = currentType;
      previousInitialDataRef.current = initialData;
      return;
    }

    const defaultsForCurrentTypeReady =
      lastDefaultsStrategyRef.current === currentType;

    // Skip if nothing meaningful changed and user has already edited params.
    if (
      !initialDataChanged &&
      currentType === previousType &&
      hasUserEditedParamsRef.current
    ) {
      previousStrategyTypeRef.current = currentType;
      previousInitialDataRef.current = initialData;
      return;
    }

    // Also skip when defaults haven't loaded yet and nothing else changed.
    const shouldApplyDefaultsUpdate =
      !initialDataChanged &&
      currentType === previousType &&
      defaultsForCurrentTypeReady;

    if (
      !initialDataChanged &&
      currentType === previousType &&
      !shouldApplyDefaultsUpdate
    ) {
      previousStrategyTypeRef.current = currentType;
      previousInitialDataRef.current = initialData;
      return;
    }

    const apiDefaults =
      defaultsForCurrentTypeReady && strategyDefaults
        ? strategyDefaults
        : undefined;
    const defaults = getDefaultParameters(
      currentType,
      strategySchema,
      apiDefaults
    );
    let nextParameters: StrategyConfig = { ...defaults };

    if (
      initialData &&
      initialData.strategy_type === currentType &&
      initialData.parameters
    ) {
      nextParameters = {
        ...defaults,
        ...initialData.parameters,
      };
    }

    setParameters(nextParameters);
    setValue('parameters', nextParameters);

    previousStrategyTypeRef.current = currentType;
    previousInitialDataRef.current = initialData;
  }, [
    selectedStrategyType,
    initialData,
    setValue,
    strategySchema,
    strategyDefaults,
  ]);

  const handleNext = async (e?: React.MouseEvent) => {
    // Prevent form submission
    e?.preventDefault();

    // Validate current step before advancing
    if (activeStep === 0) {
      const valid = await trigger(['name', 'description']);
      if (!valid) return;
    }
    if (!isEditMode && activeStep === 1) {
      const valid = await trigger(['strategy_type']);
      if (!valid) return;
    }

    setActiveStep((prev) => prev + 1);
  };

  const handleBack = (e?: React.MouseEvent) => {
    // Prevent form submission
    e?.preventDefault();
    setActiveStep((prev) => prev - 1);
  };

  const handleParameterChange = (key: string, value: unknown) => {
    hasUserEditedParamsRef.current = true;
    const newParameters: StrategyConfig = { ...parameters, [key]: value };

    // Mutual exclusion for boolean fields with exclusiveWith
    const fieldSchema = strategySchema?.properties?.[key];
    if (
      fieldSchema?.exclusiveWith &&
      fieldSchema.type === 'boolean' &&
      value === true
    ) {
      newParameters[fieldSchema.exclusiveWith] = false;
    }

    setParameters(newParameters);
    setValue('parameters', newParameters);
  };

  const handleStrategyConfigChange = (config: StrategyConfig) => {
    hasUserEditedParamsRef.current = true;
    setParameters(config);
    setValue('parameters', config);
  };

  const onFormSubmit = async (data: ConfigurationFormData) => {
    await onSubmit({
      name: data.name,
      strategy_type: data.strategy_type,
      description: data.description,
      parameters: parameters,
    });
  };

  // Different steps for create vs edit mode
  const steps = isEditMode
    ? [
        t('configuration:form.steps.basicInformation'),
        t('configuration:form.steps.parameters'),
        t('configuration:form.steps.review'),
      ]
    : [
        t('configuration:form.steps.basicInformation'),
        t('configuration:form.steps.strategyType'),
        t('configuration:form.steps.parameters'),
        t('configuration:form.steps.review'),
      ];

  const formatParameterLabel = (key: string): string => {
    const prop = strategySchema?.properties?.[key];
    if (prop) {
      const language = i18n.language;
      const localizedKey = `title_${language}` as const;
      const localizedTitle = prop[localizedKey] as string | undefined;
      if (localizedTitle) {
        return localizedTitle;
      }
      if (prop.title) {
        return prop.title;
      }
    }

    return key
      .replace(/_/g, ' ')
      .replace(/\b\w/g, (char) => char.toUpperCase());
  };

  const formatParameterGroup = (key: string): string => {
    const prop = strategySchema?.properties?.[key];
    if (!prop) {
      return t('configuration:form.otherParameters');
    }
    const language = i18n.language;
    const localizedKey = `group_${language}` as const;
    return (
      (prop[localizedKey] as string | undefined) ??
      prop.group ??
      t('configuration:form.otherParameters')
    );
  };

  const formatParameterValue = (value: unknown, key?: string): string => {
    if (Array.isArray(value)) {
      return value.join(', ');
    }

    if (typeof value === 'boolean') {
      return value ? t('common:labels.yes') : t('common:labels.no');
    }

    if (value === null || value === undefined || value === '') {
      return '-';
    }

    // Localise enum values when the schema provides enum_labels.
    if (key && typeof value === 'string') {
      const prop = strategySchema?.properties?.[key];
      if (prop?.enum && Array.isArray(prop.enum) && prop.enum.includes(value)) {
        const language = i18n.language;
        const localizedLabels = prop[`enum_labels_${language}` as const] as
          | Record<string, string>
          | undefined;
        const baseLabels = prop.enum_labels;
        const label = localizedLabels?.[value] ?? baseLabels?.[value];
        if (label) {
          return label;
        }
      }
    }

    return String(value);
  };

  const reviewParameters: Array<[string, unknown]> = strategySchema
    ? [
        ...Object.entries(strategySchema.properties)
          .filter(([key]) =>
            isParameterVisible(key, parameters, strategySchema.properties)
          )
          .map(
            ([key, prop]) =>
              [key, parameters[key] ?? prop.default] as [string, unknown]
          ),
        ...Object.entries(parameters).filter(
          ([key]) => !(key in strategySchema.properties)
        ),
      ]
    : Object.entries(parameters);

  const reviewParameterGroups = (() => {
    const groups: Array<{
      name: string;
      entries: Array<{ key: string; value: unknown }>;
    }> = [];
    const groupMap = new Map<string, Array<{ key: string; value: unknown }>>();
    const seenGroups: string[] = [];

    reviewParameters.forEach(([key, value]) => {
      const groupName = formatParameterGroup(key);
      if (!groupMap.has(groupName)) {
        groupMap.set(groupName, []);
        seenGroups.push(groupName);
      }
      groupMap.get(groupName)!.push({ key, value });
    });

    seenGroups.forEach((name) => {
      const entries = groupMap.get(name);
      if (entries && entries.length > 0) {
        groups.push({ name, entries: orderConfigEntries(entries) });
      }
    });

    return groups;
  })();

  return (
    <Box sx={{ width: '100%' }}>
      <Stepper activeStep={activeStep} sx={{ mb: 4 }}>
        {steps.map((label) => (
          <Step key={label}>
            <StepLabel>{label}</StepLabel>
          </Step>
        ))}
      </Stepper>

      <form onSubmit={handleSubmit(onFormSubmit)}>
        {/* Step 1: Basic Information */}
        {activeStep === 0 && (
          <Box>
            <Typography variant="h6" gutterBottom>
              {t('configuration:form.basicInformation')}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              {t('configuration:form.basicInfoDescription')}
            </Typography>
            <Controller<ConfigurationFormData>
              name="name"
              control={control}
              render={({ field }) => (
                <TextField
                  {...field}
                  fullWidth
                  label={t('configuration:form.configurationName')}
                  placeholder={t(
                    'configuration:form.configurationNamePlaceholder'
                  )}
                  error={!!errors.name}
                  helperText={errors.name?.message}
                  sx={{ mb: 3 }}
                />
              )}
            />
            <Controller<ConfigurationFormData>
              name="description"
              control={control}
              render={({ field }) => (
                <TextField
                  {...field}
                  fullWidth
                  label={t('configuration:form.descriptionOptional')}
                  placeholder={t('configuration:form.descriptionPlaceholder')}
                  multiline
                  rows={3}
                  error={!!errors.description}
                  helperText={errors.description?.message}
                />
              )}
            />
          </Box>
        )}

        {/* Step 2: Strategy Type (Create mode only) */}
        {!isEditMode && activeStep === 1 && (
          <Box>
            <Typography variant="h6" gutterBottom>
              {t('configuration:form.selectStrategyType')}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              {t('configuration:form.selectStrategyDescription')}
            </Typography>

            {strategiesError && (
              <Alert severity="error" sx={{ mb: 2 }}>
                {t('configuration:form.failedToLoadStrategies')}
              </Alert>
            )}

            <Controller<ConfigurationFormData>
              name="strategy_type"
              control={control}
              render={({ field }) => (
                <FormControl fullWidth error={!!errors.strategy_type}>
                  <InputLabel>
                    {t('configuration:form.strategyTypeLabel')}
                  </InputLabel>
                  <Select
                    {...field}
                    label={t('configuration:form.strategyTypeLabel')}
                    disabled={
                      !!initialData?.strategy_type || isStrategiesLoading
                    }
                  >
                    {isStrategiesLoading ? (
                      <MenuItem value="" disabled>
                        <Box
                          sx={{ display: 'flex', alignItems: 'center', gap: 2 }}
                        >
                          <CircularProgress size={16} />
                          <Typography variant="body2">
                            {t('configuration:form.loadingStrategies')}
                          </Typography>
                        </Box>
                      </MenuItem>
                    ) : (
                      selectableStrategies.map((strategy) => (
                        <MenuItem key={strategy.id} value={strategy.id}>
                          <Box>
                            <Typography variant="body2">
                              {t(
                                `strategy:types.${strategy.id}`,
                                strategy.name
                              )}
                            </Typography>
                            {!!strategy.description && (
                              <Typography
                                variant="caption"
                                color="text.secondary"
                              >
                                {t(
                                  `strategy:descriptions.${strategy.id}`,
                                  strategy.description
                                )}
                              </Typography>
                            )}
                          </Box>
                        </MenuItem>
                      ))
                    )}
                  </Select>
                  {errors.strategy_type && (
                    <Typography variant="caption" color="error" sx={{ mt: 1 }}>
                      {errors.strategy_type.message}
                    </Typography>
                  )}
                  {initialData?.strategy_type && (
                    <Typography
                      variant="caption"
                      color="text.secondary"
                      sx={{ mt: 1, display: 'block' }}
                    >
                      {t('configuration:form.strategyTypeCannotChange')}
                    </Typography>
                  )}
                </FormControl>
              )}
            />

            {selectedStrategy && (
              <Alert severity="info" sx={{ mt: 3 }}>
                <Typography variant="subtitle2" gutterBottom>
                  {t(
                    `strategy:types.${selectedStrategy.id}`,
                    selectedStrategy.name
                  )}
                </Typography>
                <Typography variant="body2">
                  {t(
                    `strategy:descriptions.${selectedStrategy.id}`,
                    selectedStrategy.description
                  )}
                </Typography>
              </Alert>
            )}
          </Box>
        )}

        {/* Step 3: Parameters (Create mode) or Step 1: Parameters (Edit mode) */}
        {((isEditMode && activeStep === 1) ||
          (!isEditMode && activeStep === 2)) && (
          <Box>
            <Typography variant="h6" gutterBottom>
              {t('configuration:form.configureParameters')}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              {t('configuration:form.configureParametersDescription', {
                strategy: selectedStrategy?.name || '',
              })}
            </Typography>
            {strategySchema ? (
              <StrategyConfigForm
                configSchema={strategySchema}
                config={parameters}
                onChange={handleStrategyConfigChange}
                disabled={isLoading}
                showValidation
              />
            ) : (
              <>
                {Object.entries(parameters).map(([key, value]) => (
                  <TextField
                    key={key}
                    fullWidth
                    label={formatParameterLabel(key)}
                    value={value as string | number}
                    onChange={(e) => {
                      const newValue =
                        typeof value === 'number'
                          ? e.target.value === ''
                            ? ''
                            : Number(e.target.value)
                          : e.target.value;
                      handleParameterChange(key, newValue);
                    }}
                    type={typeof value === 'number' ? 'number' : 'text'}
                    sx={{ mb: 2 }}
                  />
                ))}

                {Object.keys(parameters).length === 0 && (
                  <Alert severity="warning">
                    {t('configuration:empty.noParametersAvailable')}
                  </Alert>
                )}
              </>
            )}
          </Box>
        )}

        {/* Step 4: Review (Create mode) or Step 2: Review (Edit mode) */}
        {((isEditMode && activeStep === 2) ||
          (!isEditMode && activeStep === 3)) && (
          <Box>
            <Typography variant="h6" gutterBottom>
              {t('configuration:form.reviewConfiguration')}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              {t('configuration:form.reviewDescription')}
            </Typography>

            <Card variant="outlined" sx={{ mb: 2 }}>
              <CardContent>
                <Typography
                  variant="subtitle2"
                  color="text.secondary"
                  gutterBottom
                >
                  {t('common:labels.name')}
                </Typography>
                <Typography variant="body1" sx={{ mb: 2 }}>
                  {watch('name')}
                </Typography>

                {watch('description') && (
                  <>
                    <Typography
                      variant="subtitle2"
                      color="text.secondary"
                      gutterBottom
                    >
                      {t('common:labels.description')}
                    </Typography>
                    <Typography variant="body1" sx={{ mb: 2 }}>
                      {watch('description')}
                    </Typography>
                  </>
                )}

                <Typography
                  variant="subtitle2"
                  color="text.secondary"
                  gutterBottom
                >
                  {t('common:labels.strategyType')}
                </Typography>
                <Typography variant="body1" sx={{ mb: 2 }}>
                  {selectedStrategy?.name}
                </Typography>

                <Divider sx={{ my: 2 }} />

                <Typography
                  variant="subtitle2"
                  color="text.secondary"
                  gutterBottom
                >
                  {t('common:labels.parameters')}
                </Typography>
                <Box sx={{ pl: 2 }}>
                  {reviewParameterGroups.length === 0 ? (
                    <Typography variant="body2" color="text.secondary">
                      {t('configuration:empty.noParametersConfigured')}
                    </Typography>
                  ) : (
                    reviewParameterGroups.map(
                      ({ name: groupName, entries }, groupIdx) => (
                        <Box key={groupName || '__ungrouped'} sx={{ mb: 1.5 }}>
                          {groupIdx > 0 && <Divider sx={{ my: 1 }} />}
                          {groupName && (
                            <Typography
                              variant="caption"
                              color="text.secondary"
                              sx={{
                                display: 'block',
                                fontWeight: 700,
                                mb: 0.75,
                              }}
                            >
                              {groupName}
                            </Typography>
                          )}
                          {entries.map(({ key, value }) => (
                            <Box
                              key={key}
                              sx={{
                                display: 'flex',
                                justifyContent: 'space-between',
                                gap: 2,
                                mb: 0.75,
                              }}
                            >
                              <Typography
                                variant="body2"
                                color="text.secondary"
                              >
                                {formatParameterLabel(key)}:
                              </Typography>
                              <Typography
                                variant="body2"
                                fontWeight={500}
                                sx={{ textAlign: 'right' }}
                              >
                                {formatParameterValue(value, key)}
                              </Typography>
                            </Box>
                          ))}
                        </Box>
                      )
                    )
                  )}
                </Box>
              </CardContent>
            </Card>
          </Box>
        )}

        {/* Navigation Buttons */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 4 }}>
          <Button type="button" onClick={onCancel} disabled={isLoading}>
            {t('common:actions.cancel')}
          </Button>
          <Box sx={{ display: 'flex', gap: 2 }}>
            {activeStep > 0 && (
              <Button type="button" onClick={handleBack} disabled={isLoading}>
                {t('common:actions.back')}
              </Button>
            )}
            {activeStep < steps.length - 1 ? (
              <Button
                type="button"
                variant="contained"
                onClick={handleNext}
                disabled={isLoading}
              >
                {t('common:actions.next')}
              </Button>
            ) : (
              <Button
                type="submit"
                variant="contained"
                disabled={isLoading}
                startIcon={isLoading ? <CircularProgress size={20} /> : null}
              >
                {isLoading
                  ? t('common:actions.saving')
                  : t('configuration:form.saveConfiguration')}
              </Button>
            )}
          </Box>
        </Box>
      </form>
    </Box>
  );
};

export default ConfigurationForm;
