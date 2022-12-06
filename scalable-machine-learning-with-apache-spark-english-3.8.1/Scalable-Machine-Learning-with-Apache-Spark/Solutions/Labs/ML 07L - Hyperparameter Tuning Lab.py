# Databricks notebook source
# MAGIC %md-sandbox
# MAGIC 
# MAGIC <div style="text-align: center; line-height: 0; padding-top: 9px;">
# MAGIC   <img src="https://databricks.com/wp-content/uploads/2018/03/db-academy-rgb-1200px.png" alt="Databricks Learning" style="width: 600px">
# MAGIC </div>

# COMMAND ----------

# MAGIC %md # Hyperparameter Tuning with Random Forests
# MAGIC 
# MAGIC In this lab, you will convert the Airbnb problem to a classification dataset, build a random forest classifier, and tune some hyperparameters of the random forest.
# MAGIC 
# MAGIC ## ![Spark Logo Tiny](https://files.training.databricks.com/images/105/logo_spark_tiny.png) In this lesson you:<br>
# MAGIC  - Perform grid search on a random forest
# MAGIC  - Generate feature importance scores and classification metrics
# MAGIC  - Identify differences between scikit-learn's Random Forest and SparkML's
# MAGIC  
# MAGIC You can read more about the distributed implementation of Random Forests in the Spark <a href="https://github.com/apache/spark/blob/master/mllib/src/main/scala/org/apache/spark/ml/tree/impl/RandomForest.scala#L42" target="_blank">source code</a>.

# COMMAND ----------

# MAGIC %run "../Includes/Classroom-Setup"

# COMMAND ----------

# MAGIC %md ## From Regression to Classification
# MAGIC 
# MAGIC In this case, we'll turn the Airbnb housing dataset into a classification problem to **classify between high and low price listings.**  Our **`class`** column will be:<br><br>
# MAGIC 
# MAGIC - **`0`** for a low cost listing of under $150
# MAGIC - **`1`** for a high cost listing of $150 or more

# COMMAND ----------

from pyspark.ml.feature import StringIndexer, VectorAssembler
from pyspark.ml import Pipeline
from pyspark.sql.functions import col

file_path = f"{datasets_dir}/airbnb/sf-listings/sf-listings-2019-03-06-clean.delta/"

airbnb_df = (spark
            .read
            .format("delta")
            .load(file_path)
            .withColumn("priceClass", (col("price") >= 150).cast("int"))
            .drop("price")
           )

train_df, test_df = airbnb_df.randomSplit([.8, .2], seed=42)

categorical_cols = [field for (field, dataType) in train_df.dtypes if dataType == "string"]
index_output_cols = [x + "Index" for x in categorical_cols]

string_indexer = StringIndexer(inputCols=categorical_cols, outputCols=index_output_cols, handleInvalid="skip")

numeric_cols = [field for (field, dataType) in train_df.dtypes if ((dataType == "double") & (field != "priceClass"))]
assembler_inputs = index_output_cols + numeric_cols
vec_assembler = VectorAssembler(inputCols=assembler_inputs, outputCol="features")

# COMMAND ----------

# MAGIC %md ## Why can't we OHE?
# MAGIC 
# MAGIC **Question:** What would go wrong if we One Hot Encoded our variables before passing them into the random forest?
# MAGIC 
# MAGIC **HINT:** Think about what would happen to the "randomness" of feature selection.

# COMMAND ----------

# MAGIC %md ## Random Forest
# MAGIC 
# MAGIC Create a Random Forest classifer called **`rf`** with the **`labelCol=priceClass`**, **`maxBins=40`**, and **`seed=42`** (for reproducibility).
# MAGIC 
# MAGIC It's under **`pyspark.ml.classification.RandomForestClassifier`** in Python.

# COMMAND ----------

# ANSWER
from pyspark.ml.classification import RandomForestClassifier

rf = RandomForestClassifier(labelCol="priceClass", maxBins=40, seed=42)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Grid Search
# MAGIC 
# MAGIC There are a lot of hyperparameters we could tune, and it would take a long time to manually configure.
# MAGIC 
# MAGIC Let's use Spark's <a href="https://spark.apache.org/docs/latest/api/python/reference/api/pyspark.ml.tuning.ParamGridBuilder.html?highlight=paramgrid#pyspark.ml.tuning.ParamGridBuilder" target="_blank">ParamGridBuilder</a> to find the optimal hyperparameters in a more systematic approach. Call this variable **`param_grid`**.
# MAGIC 
# MAGIC Let's define a grid of hyperparameters to test:
# MAGIC   - maxDepth: max depth of the decision tree (Use the values **`2, 5, 10`**)
# MAGIC   - numTrees: number of decision trees (Use the values **`10, 20, 100`**)
# MAGIC 
# MAGIC **`addGrid()`** accepts the name of the parameter (e.g. **`rf.maxDepth`**), and a list of the possible values (e.g. **`[2, 5, 10]`**).

# COMMAND ----------

# ANSWER

from pyspark.ml.tuning import ParamGridBuilder

param_grid = (ParamGridBuilder()
              .addGrid(rf.maxDepth, [2, 5, 10])
              .addGrid(rf.numTrees, [10, 20, 100])
              .build())

# COMMAND ----------

# MAGIC %md ## Evaluator
# MAGIC 
# MAGIC In the past, we used a **`RegressionEvaluator`**.  For classification, we can use a <a href="https://spark.apache.org/docs/latest/api/python/reference/api/pyspark.ml.evaluation.BinaryClassificationEvaluator.html?highlight=binaryclass#pyspark.ml.evaluation.BinaryClassificationEvaluator" target="_blank">BinaryClassificationEvaluator</a> if we have two classes or <a href="https://spark.apache.org/docs/latest/api/python/reference/api/pyspark.ml.evaluation.MulticlassClassificationEvaluator.html?highlight=multiclass#pyspark.ml.evaluation.MulticlassClassificationEvaluator" target="_blank">MulticlassClassificationEvaluator</a> for more than two classes.
# MAGIC 
# MAGIC Create a **`BinaryClassificationEvaluator`** with **`areaUnderROC`** as the metric.
# MAGIC 
# MAGIC <img src="https://files.training.databricks.com/images/icon_note_24.png"/> <a href="https://en.wikipedia.org/wiki/Receiver_operating_characteristic" target="_blank">Read more on ROC curves here.</a>  In essence, it compares true positive and false positives.

# COMMAND ----------

# ANSWER
from pyspark.ml.evaluation import BinaryClassificationEvaluator

evaluator = BinaryClassificationEvaluator(labelCol="priceClass", metricName="areaUnderROC")

# COMMAND ----------

# MAGIC %md ## Cross Validation
# MAGIC 
# MAGIC We are going to do 3-Fold cross-validation, with **`parallelism`**=4, and set the **`seed`**=42 on the cross-validator for reproducibility.
# MAGIC 
# MAGIC Put the Random Forest in the CV to speed up the <a href="https://spark.apache.org/docs/latest/api/python/reference/api/pyspark.ml.tuning.CrossValidator.html?highlight=crossvalidator#pyspark.ml.tuning.CrossValidator" target="_blank">cross validation</a> (as opposed to the pipeline in the CV).

# COMMAND ----------

# ANSWER
from pyspark.ml.tuning import CrossValidator

cv = CrossValidator(estimator=rf, evaluator=evaluator, estimatorParamMaps=param_grid,
                    numFolds=3, parallelism=4, seed=42)

# COMMAND ----------

# MAGIC %md ## Pipeline
# MAGIC 
# MAGIC Let's fit the pipeline with our cross validator to our training data (this may take a few minutes).

# COMMAND ----------

stages = [string_indexer, vec_assembler, cv]

pipeline = Pipeline(stages=stages)

pipeline_model = pipeline.fit(train_df)

# COMMAND ----------

# MAGIC %md ## Hyperparameter
# MAGIC 
# MAGIC Which hyperparameter combination performed the best?

# COMMAND ----------

cv_model = pipeline_model.stages[-1]
rf_model = cv_model.bestModel

# list(zip(cv_model.getEstimatorParamMaps(), cv_model.avgMetrics))

print(rf_model.explainParams())

# COMMAND ----------

# MAGIC %md ## Feature Importance

# COMMAND ----------

import pandas as pd

pandas_df = pd.DataFrame(list(zip(vec_assembler.getInputCols(), rf_model.featureImportances)), columns=["feature", "importance"])
top_features = pandas_df.sort_values(["importance"], ascending=False)
top_features

# COMMAND ----------

# MAGIC %md Do those features make sense? Would you use those features when picking an Airbnb rental?

# COMMAND ----------

# MAGIC %md ## Apply Model to test set

# COMMAND ----------

# ANSWER

pred_df = pipeline_model.transform(test_df)
area_under_roc = evaluator.evaluate(pred_df)
print(f"Area under ROC is {area_under_roc:.2f}")

# COMMAND ----------

# MAGIC %md ## Save Model
# MAGIC 
# MAGIC Save the model to **`working_dir`** (variable defined in Classroom-Setup)

# COMMAND ----------

# ANSWER
pipeline_model.write().overwrite().save(working_dir)

# COMMAND ----------

# MAGIC %md ## Sklearn vs SparkML
# MAGIC 
# MAGIC <a href="https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestRegressor.html" target="_blank">Sklearn RandomForestRegressor</a> vs <a href="https://spark.apache.org/docs/latest/api/python/reference/api/pyspark.ml.regression.RandomForestRegressor.html?highlight=randomfore#pyspark.ml.regression.RandomForestRegressor" target="_blank">SparkML RandomForestRegressor</a>.
# MAGIC 
# MAGIC Look at these params in particular:
# MAGIC * **n_estimators** (sklearn) vs **numTrees** (SparkML)
# MAGIC * **max_depth** (sklearn) vs **maxDepth** (SparkML)
# MAGIC * **max_features** (sklearn) vs **featureSubsetStrategy** (SparkML)
# MAGIC * **maxBins** (SparkML only)
# MAGIC 
# MAGIC What do you notice that is different?

# COMMAND ----------

# MAGIC %md-sandbox
# MAGIC &copy; 2022 Databricks, Inc. All rights reserved.<br/>
# MAGIC Apache, Apache Spark, Spark and the Spark logo are trademarks of the <a href="https://www.apache.org/">Apache Software Foundation</a>.<br/>
# MAGIC <br/>
# MAGIC <a href="https://databricks.com/privacy-policy">Privacy Policy</a> | <a href="https://databricks.com/terms-of-use">Terms of Use</a> | <a href="https://help.databricks.com/">Support</a>
